"""
rentbuy.py — Rent vs Buy decision engine
=========================================
Compares renting (and investing what you'd have spent buying) against
buying a home with a loan.

Model (as specified):
  RENT path:
    - pay rent monthly, rent grows with rent inflation each year
    - invest the down payment you DIDN'T spend
    - each month EMI > rent, invest that surplus too (choice 1b)
    - wealth = all those investments compounding at equity return
  BUY path:
    - down payment upfront, EMI monthly
    - house appreciates
    - wealth shown TWO ways at year N:
        * "if sell" = house value - outstanding loan - 1% selling cost
        * "if hold" = house value - outstanding loan  (no selling cost)
  Excluded (by choice): maintenance, property tax, stamp duty, registration.
  A disclaimer covers those.

Outputs: monthly cost comparison + net wealth (both sell/hold) at horizon.
"""

# reuse the verified helpers from the SIP model
from model import fv_lumpsum, fv_monthly_contributions, calculate_emi


SELLING_COST_PCT = 0.01   # 1% brokerage assumption (disclaimer)


def _remaining_loan_balance(principal, annual_rate, tenure_years, at_year):
    """Outstanding loan balance after `at_year` years of EMIs."""
    if at_year >= tenure_years:
        return 0.0
    r = annual_rate / 12
    emi = calculate_emi(principal, annual_rate, tenure_years)
    balance = principal
    for _ in range(at_year * 12):
        interest = balance * r
        balance -= (emi - interest)
    return max(0.0, balance)


def rent_vs_buy(property_price, down_payment_pct, loan_rate, loan_tenure,
                monthly_rent, rent_growth, property_appreciation,
                equity_return, horizons=(10, 15, 20)):
    """
    Returns a dict with, for each horizon:
      rent_wealth, buy_wealth_sell, buy_wealth_hold,
      and monthly cost info.
    """
    down_payment = property_price * down_payment_pct
    loan_amount  = property_price - down_payment
    emi = calculate_emi(loan_amount, loan_rate, loan_tenure)

    out = {"emi": emi, "down_payment": down_payment,
           "loan_amount": loan_amount, "horizons": horizons, "years": {}}

    for N in horizons:
        # ---------- RENT PATH ----------
        # 1) down payment invested as a lump sum for N years
        dp_fv = fv_lumpsum(down_payment, equity_return, N)

        # 2) monthly surplus (EMI - rent) invested, year by year,
        #    because rent grows each year so the surplus changes.
        surplus_fv = 0.0
        for y in range(N):
            rent_this_year = monthly_rent * ((1 + rent_growth) ** y)
            monthly_surplus = emi - rent_this_year      # may be negative later
            if monthly_surplus > 0:
                # invest this year's 12 monthly surpluses, then grow to horizon
                one_year = fv_monthly_contributions(monthly_surplus, equity_return, 1)
                surplus_fv += fv_lumpsum(one_year, equity_return, N - y - 1)
            # if surplus < 0 (rent > emi), renter has no surplus to invest that year

        rent_wealth = dp_fv + surplus_fv

        # ---------- BUY PATH ----------
        house_value = property_price * ((1 + property_appreciation) ** N)
        outstanding = _remaining_loan_balance(loan_amount, loan_rate, loan_tenure, N)
        equity_hold = house_value - outstanding
        equity_sell = house_value * (1 - SELLING_COST_PCT) - outstanding

        # ---------- MONTHLY COST (at year N) ----------
        rent_at_N = monthly_rent * ((1 + rent_growth) ** (N - 1))
        emi_cost = emi if N <= loan_tenure else 0.0

        out["years"][N] = {
            "rent_wealth": rent_wealth,
            "buy_wealth_sell": equity_sell,
            "buy_wealth_hold": equity_hold,
            "house_value": house_value,
            "outstanding_loan": outstanding,
            "monthly_rent_at_year": rent_at_N,
            "monthly_emi": emi_cost,
        }

    return out


# ==========================================================
# SANITY CHECKS
# ==========================================================
if __name__ == "__main__":
    # A realistic example:
    # ₹1cr house, 20% down, 9% loan 20yr, ₹30k rent growing 5%/yr,
    # house appreciates 7%/yr, investments return 12%/yr.
    r = rent_vs_buy(
        property_price=10_000_000, down_payment_pct=0.20,
        loan_rate=0.09, loan_tenure=20,
        monthly_rent=30_000, rent_growth=0.05,
        property_appreciation=0.07, equity_return=0.12,
        horizons=(10, 15, 20),
    )

    print(f"Property: ₹1,00,00,000 | Down: ₹{r['down_payment']:,.0f} | "
          f"Loan: ₹{r['loan_amount']:,.0f} | EMI: ₹{r['emi']:,.0f}\n")

    print(f"{'Year':<6}{'Rent wealth':>16}{'Buy (sell)':>16}{'Buy (hold)':>16}{'Winner':>10}")
    for N in r["horizons"]:
        y = r["years"][N]
        winner = "Buy" if y["buy_wealth_hold"] > y["rent_wealth"] else "Rent"
        print(f"{N:<6}{y['rent_wealth']:>16,.0f}{y['buy_wealth_sell']:>16,.0f}"
              f"{y['buy_wealth_hold']:>16,.0f}{winner:>10}")

    print("\nMonthly cost at each horizon:")
    for N in r["horizons"]:
        y = r["years"][N]
        print(f"  Year {N}: rent ₹{y['monthly_rent_at_year']:,.0f}  vs  "
              f"EMI ₹{y['monthly_emi']:,.0f}")

    print("\n--- SANITY CHECKS ---")
    # 1) EMI on 80L at 9% for 20yr
    from model import calculate_emi
    emi_check = calculate_emi(8_000_000, 0.09, 20)
    print(f"EMI 80L@9%/20yr = ₹{emi_check:,.0f} (expect ~71,978)")

    # 2) at year 20 loan fully paid -> outstanding should be 0
    y20 = r["years"][20]
    print(f"Outstanding loan at yr20 = ₹{y20['outstanding_loan']:,.0f} (expect 0)")

    # 3) buy_wealth_hold should exceed buy_wealth_sell by ~1% of house value
    diff = y20["buy_wealth_hold"] - y20["buy_wealth_sell"]
    expected = y20["house_value"] * 0.01
    print(f"hold - sell = ₹{diff:,.0f}  vs  1% house value ₹{expected:,.0f} "
          f"({'OK' if abs(diff-expected) < 2 else 'MISMATCH'})")

    # 4) house value at yr20 = 1cr * 1.07^20
    hv = 10_000_000 * (1.07**20)
    print(f"House value yr20 = ₹{y20['house_value']:,.0f} (expect ₹{hv:,.0f}) "
          f"({'OK' if abs(y20['house_value']-hv) < 2 else 'MISMATCH'})")