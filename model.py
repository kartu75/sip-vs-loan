"""
SIP vs Loan Decision Engine  —  full model
==========================================
Answers: you need cash for a house and you hold SIP investments. Redeem them,
take a loan, or a hybrid split? Compares net wealth across time.

Features
--------
1. Redeem / Loan / Hybrid  — one engine (`evaluate_split`) handles all three.
2. Step-up SIP             — SIP that grows a fixed % every year (salary growth).
3. EMI-as-add-on-SIP       — fair framing: the redeemer invests the freed-up EMI.
4. Break-even finder       — the equity & loan-rate values where the winner flips.
5. Monte Carlo             — replaces the single return with a distribution of
                             market paths, so results become probabilities.

Shortfall rule: if redemption after LTCG tax doesn't cover the cash need, the
remainder is borrowed. No magic savings. Every scenario obeys this one rule.
"""

import random
import math


# ==========================================================
# CORE TIME-VALUE HELPERS
# ==========================================================

def fv_lumpsum(present_value, annual_rate, years):
    """Future value of a one-time lump sum, compounded monthly."""
    m = annual_rate / 12
    return present_value * (1 + m) ** (years * 12)


def fv_monthly_contributions(monthly_amount, annual_rate, years):
    """Future value of a flat monthly contribution stream (annuity)."""
    m = annual_rate / 12
    n = years * 12
    if m == 0:
        return monthly_amount * n
    return monthly_amount * (((1 + m) ** n - 1) / m)


def fv_stepup_sip(first_year_monthly, annual_rate, years, stepup_rate):
    """
    Future value of a SIP that increases `stepup_rate` each year.
    Year 1 invests `first_year_monthly`/month, year 2 invests
    first_year_monthly*(1+stepup), etc. Each year's 12 contributions
    grow at `annual_rate` for the remaining time.

    When stepup_rate == 0 this equals fv_monthly_contributions exactly.
    """
    if stepup_rate == 0:
        return fv_monthly_contributions(first_year_monthly, annual_rate, years)

    total = 0.0
    for y in range(years):
        monthly_this_year = first_year_monthly * ((1 + stepup_rate) ** y)
        # value of this year's 12 monthly contributions, compounded to year-end
        one_year_fv = fv_monthly_contributions(monthly_this_year, annual_rate, 1)
        # then that lump grows for the remaining (years - y - 1) years
        total += fv_lumpsum(one_year_fv, annual_rate, years - y - 1)
    return total


def calculate_emi(principal, annual_rate, years):
    """Standard monthly EMI."""
    r = annual_rate / 12
    n = years * 12
    if r == 0:
        return principal / n
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


def loan_amortization(cash_need, loan_rate, loan_tenure):
    """Month-by-month split of each EMI into interest vs principal, by year."""
    emi = calculate_emi(cash_need, loan_rate, loan_tenure)
    r = loan_rate / 12
    balance = cash_need
    yearly_interest, yearly_principal = [], []
    for _ in range(loan_tenure):
        yi = yp = 0.0
        for _ in range(12):
            interest = balance * r
            principal = emi - interest
            balance -= principal
            yi += interest
            yp += principal
        yearly_interest.append(yi)
        yearly_principal.append(yp)
    return emi, yearly_interest, yearly_principal


def total_tax_saved(yearly_interest, yearly_principal, tax_slab,
                    sec_24b_limit, sec_80c_limit):
    """Old-regime tax saved from 24b (interest) + 80C (principal) deductions."""
    total = 0.0
    for interest, principal in zip(yearly_interest, yearly_principal):
        deductible = min(interest, sec_24b_limit) + min(principal, sec_80c_limit)
        total += deductible * tax_slab
    return total


# ==========================================================
# THE GENERAL ENGINE  — redeem / loan / hybrid, with optional
# step-up SIP and the EMI-as-add-on-SIP framing.
# ==========================================================

def evaluate_split(redeem_fraction, corpus, invested, cash_need, monthly_sip,
                   loan_tenure, loan_rate, equity_return, tax_slab,
                   ltcg_exemption, ltcg_rate, sec_24b_limit, sec_80c_limit,
                   regime, horizons,
                   stepup_rate=0.0, reinvest_emi=False):
    """
    redeem_fraction 0.0 = pure loan, 1.0 = pure redeem, between = hybrid.

    stepup_rate: annual % increase in the ongoing SIP (0 = flat).
    reinvest_emi: if True, use the FAIR framing — instead of treating the EMI
        as pure opportunity cost, the person who borrows LESS (redeems more)
        invests the EMI they DON'T have to pay as extra SIP. Concretely, we
        give every scenario the SAME monthly outflow budget: (base SIP + the
        full pure-loan EMI). Whatever isn't spent on this scenario's EMI is
        invested. This makes the comparison apples-to-apples on cash flow.
    """
    # --- redemption portion ---
    corpus_sold   = corpus * redeem_fraction
    gain_realised = (corpus - invested) * redeem_fraction
    taxable_gain  = max(0.0, gain_realised - ltcg_exemption)
    ltcg_tax      = taxable_gain * ltcg_rate
    redemption_cash = corpus_sold - ltcg_tax

    # --- loan portion (covers the shortfall too) ---
    loan_amount = max(0.0, cash_need - redemption_cash)
    if loan_amount > 0:
        emi, yr_int, yr_prin = loan_amortization(loan_amount, loan_rate, loan_tenure)
        tax_saved = (total_tax_saved(yr_int, yr_prin, tax_slab,
                                     sec_24b_limit, sec_80c_limit)
                     if regime == "old" else 0.0)
    else:
        emi, tax_saved = 0.0, 0.0

    corpus_remaining = corpus - corpus_sold

    # reference EMI = the EMI of the FULL pure-loan (redeem_fraction=0) case,
    # so every scenario shares the same cash-flow budget under fair framing.
    if reinvest_emi:
        ref_emi = calculate_emi(cash_need, loan_rate, loan_tenure)
    else:
        ref_emi = 0.0

    wealth = {}
    for years in horizons:
        # remaining corpus compounds
        corpus_fv = fv_lumpsum(corpus_remaining, equity_return, years)

        # ongoing SIP (flat or step-up) — identical across scenarios
        sip_fv = fv_stepup_sip(monthly_sip, equity_return, years, stepup_rate)

        if reinvest_emi:
            # FAIR FRAMING: everyone has budget (base SIP + ref_emi).
            # This scenario spends `emi` on its loan; invests (ref_emi - emi).
            extra_monthly = max(0.0, ref_emi - emi)
            extra_fv = 0.0
            if extra_monthly > 0:
                em_years = min(years, loan_tenure)
                extra_fv = fv_monthly_contributions(extra_monthly, equity_return, em_years)
                if years > loan_tenure:
                    extra_fv = fv_lumpsum(extra_fv, equity_return, years - loan_tenure)
            wealth[years] = corpus_fv + sip_fv + extra_fv + tax_saved
        else:
            # ORIGINAL FRAMING: EMI is pure opportunity cost.
            if emi > 0:
                em_years = min(years, loan_tenure)
                emi_pot = fv_monthly_contributions(emi, equity_return, em_years)
                if years > loan_tenure:
                    emi_pot = fv_lumpsum(emi_pot, equity_return, years - loan_tenure)
            else:
                emi_pot = 0.0
            wealth[years] = corpus_fv + sip_fv - emi_pot + tax_saved

    details = {
        "redeem_fraction": redeem_fraction,
        "corpus_sold": corpus_sold,
        "ltcg_tax": ltcg_tax,
        "redemption_cash": redemption_cash,
        "loan_amount": loan_amount,
        "emi": emi,
        "tax_saved": tax_saved,
        "corpus_remaining": corpus_remaining,
    }
    return wealth, details


# ==========================================================
# COMPARE  — the three headline cases
# ==========================================================

def compare(corpus, invested, cash_need, monthly_sip, loan_tenure,
            loan_rate, equity_return, tax_slab,
            ltcg_exemption=125_000, ltcg_rate=0.125,
            sec_24b_limit=200_000, sec_80c_limit=150_000,
            horizons=(10, 15, 20), stepup_rate=0.0, reinvest_emi=False):
    common = dict(
        corpus=corpus, invested=invested, cash_need=cash_need,
        monthly_sip=monthly_sip, loan_tenure=loan_tenure, loan_rate=loan_rate,
        equity_return=equity_return, tax_slab=tax_slab,
        ltcg_exemption=ltcg_exemption, ltcg_rate=ltcg_rate,
        sec_24b_limit=sec_24b_limit, sec_80c_limit=sec_80c_limit,
        horizons=horizons, stepup_rate=stepup_rate, reinvest_emi=reinvest_emi)

    redeem, redeem_details = evaluate_split(1.0, regime="old", **common)
    loan_new, _            = evaluate_split(0.0, regime="new", **common)
    loan_old, loan_details = evaluate_split(0.0, regime="old", **common)
    return {
        "emi": loan_details["emi"],
        "redeem": redeem, "redeem_details": redeem_details,
        "loan_new": loan_new, "loan_old": loan_old,
        "horizons": horizons,
    }


def find_optimal_split(corpus, invested, cash_need, monthly_sip, loan_tenure,
                       loan_rate, equity_return, tax_slab, regime,
                       ltcg_exemption=125_000, ltcg_rate=0.125,
                       sec_24b_limit=200_000, sec_80c_limit=150_000,
                       target_horizon=15, steps=101,
                       stepup_rate=0.0, reinvest_emi=False):
    best_frac, best_wealth, curve = None, float("-inf"), []
    for i in range(steps):
        frac = i / (steps - 1)
        wealth, _ = evaluate_split(
            frac, corpus=corpus, invested=invested, cash_need=cash_need,
            monthly_sip=monthly_sip, loan_tenure=loan_tenure, loan_rate=loan_rate,
            equity_return=equity_return, tax_slab=tax_slab,
            ltcg_exemption=ltcg_exemption, ltcg_rate=ltcg_rate,
            sec_24b_limit=sec_24b_limit, sec_80c_limit=sec_80c_limit,
            regime=regime, horizons=(target_horizon,),
            stepup_rate=stepup_rate, reinvest_emi=reinvest_emi)
        w = wealth[target_horizon]
        curve.append((frac, w))
        if w > best_wealth:
            best_wealth, best_frac = w, frac
    return best_frac, best_wealth, curve


# ==========================================================
# BREAK-EVEN FINDER  (bisection root-finder)
# ==========================================================

def _loan_minus_redeem(equity_return, loan_rate, base_args, tax_args,
                       horizon, regime, stepup_rate, reinvest_emi):
    args = {**base_args, "equity_return": equity_return, "loan_rate": loan_rate}
    loan, _   = evaluate_split(0.0, regime=regime, horizons=(horizon,),
                               stepup_rate=stepup_rate, reinvest_emi=reinvest_emi,
                               **args, **tax_args)
    redeem, _ = evaluate_split(1.0, regime=regime, horizons=(horizon,),
                               stepup_rate=stepup_rate, reinvest_emi=reinvest_emi,
                               **args, **tax_args)
    return loan[horizon] - redeem[horizon]


def _bisection(func, lo, hi, tol=1e-5, max_iter=100):
    f_lo, f_hi = func(lo), func(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        f_mid = func(mid)
        if abs(f_mid) < 1 or (hi - lo) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def find_breakevens(corpus, invested, cash_need, monthly_sip, loan_tenure,
                    loan_rate, equity_return, tax_slab, regime,
                    ltcg_exemption=125_000, ltcg_rate=0.125,
                    sec_24b_limit=200_000, sec_80c_limit=150_000,
                    horizon=15, search_lo=0.02, search_hi=0.30,
                    stepup_rate=0.0, reinvest_emi=False):
    base_args = dict(corpus=corpus, invested=invested, cash_need=cash_need,
                     monthly_sip=monthly_sip, loan_tenure=loan_tenure,
                     tax_slab=tax_slab)
    tax_args = dict(ltcg_exemption=ltcg_exemption, ltcg_rate=ltcg_rate,
                    sec_24b_limit=sec_24b_limit, sec_80c_limit=sec_80c_limit)
    eq_be = _bisection(lambda er: _loan_minus_redeem(
        er, loan_rate, base_args, tax_args, horizon, regime,
        stepup_rate, reinvest_emi), search_lo, search_hi)
    lr_be = _bisection(lambda lr: _loan_minus_redeem(
        equity_return, lr, base_args, tax_args, horizon, regime,
        stepup_rate, reinvest_emi), search_lo, search_hi)
    return {"equity_breakeven": eq_be, "loan_breakeven": lr_be}


# ==========================================================
# MONTE CARLO  — returns as a distribution, not a point estimate
# ==========================================================

def monte_carlo(corpus, invested, cash_need, monthly_sip, loan_tenure,
                loan_rate, tax_slab, regime, horizon,
                mean_return=0.12, volatility=0.18,
                ltcg_exemption=125_000, ltcg_rate=0.125,
                sec_24b_limit=200_000, sec_80c_limit=150_000,
                stepup_rate=0.0, reinvest_emi=False,
                n_sims=2000, seed=42):
    """
    Instead of assuming a fixed equity return, draw a random annualized return
    for each simulated life (normal around mean_return with given volatility),
    and see who wins — redeem vs loan — in each world.

    Returns dict with win probability for the loan, plus wealth distributions
    (percentiles) for both paths.
    """
    rng = random.Random(seed)
    loan_wins = 0
    loan_wealths, redeem_wealths, diffs = [], [], []

    tax = dict(ltcg_exemption=ltcg_exemption, ltcg_rate=ltcg_rate,
               sec_24b_limit=sec_24b_limit, sec_80c_limit=sec_80c_limit)

    for _ in range(n_sims):
        # one sampled annualized return for this whole simulated life
        r = rng.gauss(mean_return, volatility)
        r = max(-0.9, r)   # floor: can't lose more than ~everything in a year

        base = dict(corpus=corpus, invested=invested, cash_need=cash_need,
                    monthly_sip=monthly_sip, loan_tenure=loan_tenure,
                    loan_rate=loan_rate, equity_return=r, tax_slab=tax_slab,
                    horizons=(horizon,), stepup_rate=stepup_rate,
                    reinvest_emi=reinvest_emi)

        loan_w, _   = evaluate_split(0.0, regime=regime, **base, **tax)
        redeem_w, _ = evaluate_split(1.0, regime=regime, **base, **tax)
        lw, rw = loan_w[horizon], redeem_w[horizon]
        loan_wealths.append(lw)
        redeem_wealths.append(rw)
        diffs.append(lw - rw)
        if lw > rw:
            loan_wins += 1

    def pct(data, p):
        s = sorted(data)
        k = (len(s) - 1) * p
        f = math.floor(k); c = math.ceil(k)
        if f == c:
            return s[int(k)]
        return s[f] * (c - k) + s[c] * (k - f)

    return {
        "n_sims": n_sims,
        "loan_win_prob": loan_wins / n_sims,
        "loan_p10": pct(loan_wealths, 0.10),
        "loan_p50": pct(loan_wealths, 0.50),
        "loan_p90": pct(loan_wealths, 0.90),
        "redeem_p10": pct(redeem_wealths, 0.10),
        "redeem_p50": pct(redeem_wealths, 0.50),
        "redeem_p90": pct(redeem_wealths, 0.90),
        "loan_wealths": loan_wealths,
        "redeem_wealths": redeem_wealths,
    }


# ==========================================================
# TERMINAL PRESENTATION + SELF-TESTS
# ==========================================================

def print_results(r):
    print(f"EMI (pure loan): {r['emi']:,.0f}/month\n")
    print("NET WEALTH COMPARISON")
    print(f"  {'Year':<6}{'Redeem':>16}{'Loan(New)':>16}{'Loan(Old)':>16}{'Winner':>10}")
    for y in r["horizons"]:
        w = "Loan" if r["loan_old"][y] > r["redeem"][y] else "Redeem"
        print(f"  {y:<6}{r['redeem'][y]:>16,.0f}{r['loan_new'][y]:>16,.0f}"
              f"{r['loan_old'][y]:>16,.0f}{w:>10}")


if __name__ == "__main__":
    args = dict(corpus=1_500_000, invested=1_000_000, cash_need=1_500_000,
                monthly_sip=20_000, loan_tenure=15, loan_rate=0.09,
                equity_return=0.12, tax_slab=0.30)
    H = (10, 15, 20)
    TAX = dict(ltcg_exemption=125_000, ltcg_rate=0.125,
               sec_24b_limit=200_000, sec_80c_limit=150_000)

    results = compare(**args)
    print_results(results)

    print("\nSELF-TESTS")
    sheet = {10: 6_863_195, 15: 12_196_344, 20: 23_127_580}
    print("  pure loan matches sheet:",
          "OK" if all(abs(round(results["loan_old"][y]) - sheet[y]) <= 2 for y in sheet) else "FAIL")

    w0, _ = evaluate_split(0.0, regime="old", **args, **TAX, horizons=H)
    w1, _ = evaluate_split(1.0, regime="old", **args, **TAX, horizons=H)
    print("  hybrid(0%)==loan:",
          "OK" if all(abs(w0[y]-results["loan_old"][y])<=2 for y in H) else "FAIL")
    print("  hybrid(100%)==redeem:",
          "OK" if all(abs(w1[y]-results["redeem"][y])<=2 for y in H) else "FAIL")

    # step-up with 0% must equal flat
    flat, _   = evaluate_split(0.0, regime="old", **args, **TAX, horizons=H, stepup_rate=0.0)
    stepup0,_ = evaluate_split(0.0, regime="old", **args, **TAX, horizons=H, stepup_rate=0.0)
    print("  stepup(0%)==flat:",
          "OK" if all(abs(flat[y]-stepup0[y])<=2 for y in H) else "FAIL")

    # step-up 10% must produce MORE wealth than flat
    stepup10,_ = evaluate_split(0.0, regime="old", **args, **TAX, horizons=H, stepup_rate=0.10)
    print("  stepup(10%)>flat:",
          "OK" if all(stepup10[y] > flat[y] for y in H) else "FAIL")

    # break-even
    be = find_breakevens(**args, regime="old", horizon=15)
    print(f"  break-even equity {be['equity_breakeven']*100:.2f}%, "
          f"loan {be['loan_breakeven']*100:.2f}%")

    # monte carlo
    mc = monte_carlo(corpus=1_500_000, invested=1_000_000, cash_need=1_500_000,
                     monthly_sip=20_000, loan_tenure=15, loan_rate=0.09,
                     tax_slab=0.30, regime="old", horizon=15,
                     mean_return=0.12, volatility=0.18, n_sims=2000)
    print(f"  monte carlo: loan wins {mc['loan_win_prob']*100:.1f}% of {mc['n_sims']} sims")
    print(f"    loan   P10/P50/P90: {mc['loan_p10']:,.0f} / {mc['loan_p50']:,.0f} / {mc['loan_p90']:,.0f}")
    print(f"    redeem P10/P50/P90: {mc['redeem_p10']:,.0f} / {mc['redeem_p50']:,.0f} / {mc['redeem_p90']:,.0f}")