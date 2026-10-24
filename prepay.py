"""
prepay.py — Prepay Loan vs Invest Surplus decision engine (Module 4, MANKART)

Verified against a hand-built Google Sheets model with these reference inputs:
    Outstanding loan:      Rs 50,00,000
    Loan rate:             9.00% p.a.
    Remaining tenure:      15 years (180 months)
    Surplus available:     Rs 5,00,000 (one-time)
    Equity return assumed: 12.00% p.a.
    Tax slab:               30%
    Sec 24(b) cap:          Rs 2,00,000 / year

Expected outputs (sheet ground truth):
    Baseline total interest (no prepay):        Rs 41,28,399
    Option 1 (Reduced EMI)    total interest:   Rs 37,15,559   -> saved Rs 4,12,840
    Option 2 (Reduced Tenure) total interest:   Rs 29,32,839   -> saved Rs 11,95,560
    Option 1 tax deduction lost:                Rs 16,964
    Option 2 tax deduction lost:                Rs 1,67,865
    Option 1 effective net benefit:             Rs 3,95,877
    Option 2 effective net benefit:             Rs 10,27,695
    Option 2 new tenure:                        147 months (33 months early)
    Invest terminal value (annual compounding): Rs 27,36,783
    Invest terminal value (monthly compounding):Rs 29,97,901
"""

from dataclasses import dataclass, field


# ==========================================================
# AMORTIZATION HELPERS
# ==========================================================

def emi_amount(principal, annual_rate, months):
    """Standard EMI formula."""
    if months <= 0:
        return 0.0
    r = annual_rate / 12
    if r == 0:
        return principal / months
    return principal * r * (1 + r) ** months / ((1 + r) ** months - 1)


def amortize(principal, annual_rate, emi, max_months):
    """
    Run a loan forward month by month at a fixed EMI until the balance
    hits zero (or max_months is reached, whichever is first).

    Returns a list of dicts: month, opening, interest, principal_paid, closing
    and the totals (total_interest, months_taken).
    """
    r = annual_rate / 12
    balance = principal
    schedule = []
    month = 0
    while balance > 0.5 and month < max_months:
        month += 1
        interest = balance * r
        principal_paid = emi - interest
        if principal_paid > balance:
            # final partial installment
            principal_paid = balance
            this_emi = principal_paid + interest
        else:
            this_emi = emi
        closing = balance - principal_paid
        schedule.append({
            "month": month,
            "opening": balance,
            "emi": this_emi,
            "interest": interest,
            "principal_paid": principal_paid,
            "closing": max(closing, 0.0),
        })
        balance = closing
    total_interest = sum(row["interest"] for row in schedule)
    return schedule, total_interest, month


def annual_interest_from_schedule(schedule):
    """Bucket a monthly schedule's interest into calendar loan-years (12-month blocks)."""
    years = {}
    for row in schedule:
        year = (row["month"] - 1) // 12 + 1
        years[year] = years.get(year, 0.0) + row["interest"]
    return years


def sec24b_deduction_and_loss(annual_interest_map, cap, tax_slab):
    """
    For each loan-year, the claimable deduction is min(interest, cap).
    Tax benefit "lost" only happens when interest for that year falls
    below the cap (i.e., less deduction available than in the baseline
    year for the same period) -- computed by the caller as a diff
    against baseline annual interest, not in isolation here.
    """
    claim = {y: min(i, cap) for y, i in annual_interest_map.items()}
    total_claim = sum(claim.values())
    return claim, total_claim


def tax_benefit_lost(baseline_annual, scenario_annual, cap, tax_slab):
    """
    Tax lost in a year = tax_slab * (baseline_claim - scenario_claim), floored at 0.
    A shortened loan (scenario ends early) contributes zero interest/claim
    in years the baseline still had interest -- that lost claim also counts.
    """
    all_years = set(baseline_annual) | set(scenario_annual)
    total_lost = 0.0
    for y in sorted(all_years):
        base_claim = min(baseline_annual.get(y, 0.0), cap)
        scen_claim = min(scenario_annual.get(y, 0.0), cap)
        lost = max(0.0, base_claim - scen_claim) * tax_slab
        total_lost += lost
    return total_lost


# ==========================================================
# SCENARIO A: PREPAY
# ==========================================================

@dataclass
class PrepayResult:
    label: str
    new_principal: float
    monthly_payment: float
    tenure_months: int
    total_interest: float
    interest_saved: float
    tax_deduction_lost: float
    effective_benefit: float
    schedule: list = field(default_factory=list)


def evaluate_prepay(principal, annual_rate, tenure_months, surplus,
                     tax_slab, sec24b_cap):
    """
    Computes the baseline (no prepay) and both prepay options, with
    Sec 24(b) tax adjustment, exactly mirroring the verified sheet.
    """
    baseline_emi = emi_amount(principal, annual_rate, tenure_months)
    baseline_schedule, baseline_interest, baseline_months = amortize(
        principal, annual_rate, baseline_emi, tenure_months)
    baseline_annual = annual_interest_from_schedule(baseline_schedule)

    new_principal = principal - surplus

    # Option 1: Reduced EMI, same tenure
    opt1_emi = emi_amount(new_principal, annual_rate, tenure_months)
    opt1_schedule, opt1_interest, opt1_months = amortize(
        new_principal, annual_rate, opt1_emi, tenure_months)
    opt1_annual = annual_interest_from_schedule(opt1_schedule)
    opt1_tax_lost = tax_benefit_lost(baseline_annual, opt1_annual, sec24b_cap, tax_slab)
    opt1_interest_saved = baseline_interest - opt1_interest
    opt1_net_benefit = opt1_interest_saved - opt1_tax_lost

    opt1 = PrepayResult(
        label="Reduced EMI",
        new_principal=new_principal,
        monthly_payment=opt1_emi,
        tenure_months=opt1_months,
        total_interest=opt1_interest,
        interest_saved=opt1_interest_saved,
        tax_deduction_lost=opt1_tax_lost,
        effective_benefit=opt1_net_benefit,
        schedule=opt1_schedule,
    )

    # Option 2: Same EMI as baseline, reduced tenure (early payoff)
    opt2_schedule, opt2_interest, opt2_months = amortize(
        new_principal, annual_rate, baseline_emi, tenure_months)
    opt2_annual = annual_interest_from_schedule(opt2_schedule)
    opt2_tax_lost = tax_benefit_lost(baseline_annual, opt2_annual, sec24b_cap, tax_slab)
    opt2_interest_saved = baseline_interest - opt2_interest
    opt2_net_benefit = opt2_interest_saved - opt2_tax_lost

    opt2 = PrepayResult(
        label="Reduced Tenure",
        new_principal=new_principal,
        monthly_payment=baseline_emi,
        tenure_months=opt2_months,
        total_interest=opt2_interest,
        interest_saved=opt2_interest_saved,
        tax_deduction_lost=opt2_tax_lost,
        effective_benefit=opt2_net_benefit,
        schedule=opt2_schedule,
    )

    baseline = {
        "emi": baseline_emi,
        "tenure_months": baseline_months,
        "total_interest": baseline_interest,
    }

    return baseline, opt1, opt2


# ==========================================================
# SCENARIO B: INVEST
# ==========================================================

def invest_terminal_value(surplus, annual_return, years, compounding="annual"):
    """
    compounding: "annual" -> P*(1+r)^t
                 "monthly" -> P*(1+r/12)^(12t)
    """
    if compounding == "monthly":
        n = 12
        return surplus * (1 + annual_return / n) ** (n * years)
    return surplus * (1 + annual_return) ** years


# ==========================================================
# BREAKEVEN
# ==========================================================

def breakeven_return(surplus, years, target_benefit, compounding="annual", tol=1e-6):
    """
    Solve for the equity return r such that terminal net gain
    (terminal_value - surplus) == target_benefit, via bisection.
    """
    lo, hi = -0.5, 2.0

    def net_gain(r):
        return invest_terminal_value(surplus, r, years, compounding) - surplus - target_benefit

    if net_gain(lo) > 0 or net_gain(hi) < 0:
        return None  # no root in range

    for _ in range(200):
        mid = (lo + hi) / 2
        val = net_gain(mid)
        if abs(val) < tol:
            return mid
        if val > 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


# ==========================================================
# TOP-LEVEL: FULL COMPARISON
# ==========================================================

def compare_prepay_vs_invest(principal, annual_rate, tenure_months, surplus,
                              tax_slab, sec24b_cap, equity_return):
    years = tenure_months / 12
    baseline, opt1, opt2 = evaluate_prepay(
        principal, annual_rate, tenure_months, surplus, tax_slab, sec24b_cap)

    invest_annual = invest_terminal_value(surplus, equity_return, years, "annual")
    invest_monthly = invest_terminal_value(surplus, equity_return, years, "monthly")

    be_opt1 = breakeven_return(surplus, years, opt1.effective_benefit, "annual")
    be_opt2 = breakeven_return(surplus, years, opt2.effective_benefit, "annual")

    return {
        "baseline": baseline,
        "option1_reduced_emi": opt1,
        "option2_reduced_tenure": opt2,
        "invest_terminal_annual": invest_annual,
        "invest_terminal_monthly": invest_monthly,
        "invest_net_gain_annual": invest_annual - surplus,
        "breakeven_return_vs_opt1": be_opt1,
        "breakeven_return_vs_opt2": be_opt2,
        "winner_vs_opt1": "invest" if invest_annual - surplus > opt1.effective_benefit else "prepay_opt1",
        "winner_vs_opt2": "invest" if invest_annual - surplus > opt2.effective_benefit else "prepay_opt2",
    }


# ==========================================================
# VERIFICATION AGAINST THE SHEET
# ==========================================================

if __name__ == "__main__":
    result = compare_prepay_vs_invest(
        principal=5_000_000,
        annual_rate=0.09,
        tenure_months=180,
        surplus=500_000,
        tax_slab=0.30,
        sec24b_cap=200_000,
        equity_return=0.12,
    )

    b = result["baseline"]
    o1 = result["option1_reduced_emi"]
    o2 = result["option2_reduced_tenure"]

    def fmt(x):
        return f"Rs {x:,.0f}"

    print("=== BASELINE (no prepay) ===")
    print(f"EMI: {fmt(b['emi'])} | Tenure: {b['tenure_months']} mo | Total interest: {fmt(b['total_interest'])}")
    print("Expected: EMI ~50,713 | Tenure 180 | Total interest ~41,28,399\n")

    print("=== OPTION 1: Reduced EMI ===")
    print(f"New EMI: {fmt(o1.monthly_payment)} | Total interest: {fmt(o1.total_interest)}")
    print(f"Interest saved: {fmt(o1.interest_saved)} | Tax lost: {fmt(o1.tax_deduction_lost)} | Net benefit: {fmt(o1.effective_benefit)}")
    print("Expected: EMI ~45,642 | Total interest ~37,15,559 | Saved ~4,12,840 | Tax lost ~16,964 | Net ~3,95,877\n")

    print("=== OPTION 2: Reduced Tenure ===")
    print(f"Tenure: {o2.tenure_months} mo | Total interest: {fmt(o2.total_interest)}")
    print(f"Interest saved: {fmt(o2.interest_saved)} | Tax lost: {fmt(o2.tax_deduction_lost)} | Net benefit: {fmt(o2.effective_benefit)}")
    print("Expected: Tenure 147 | Total interest ~29,32,839 | Saved ~11,95,560 | Tax lost ~1,67,865 | Net ~10,27,695\n")

    print("=== INVEST ===")
    print(f"Terminal (annual comp): {fmt(result['invest_terminal_annual'])}")
    print(f"Terminal (monthly comp): {fmt(result['invest_terminal_monthly'])}")
    print("Expected: annual ~27,36,783 | monthly ~29,97,901\n")

    print("=== VERDICT ===")
    print(f"Invest net gain (annual): {fmt(result['invest_net_gain_annual'])}")
    print(f"Winner vs Opt1: {result['winner_vs_opt1']} | Winner vs Opt2: {result['winner_vs_opt2']}")
    print(f"Breakeven return vs Opt1: {result['breakeven_return_vs_opt1']*100:.2f}% | vs Opt2: {result['breakeven_return_vs_opt2']*100:.2f}%")
    print("Expected breakeven: ~3.96% vs Opt1 | ~7.73% vs Opt2")