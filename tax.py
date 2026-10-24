"""
tax.py — Old vs New Tax Regime decision engine (Module 5, MANKART)

Computes income tax liability under both the Old and New regimes
(FY 2024-25 / AY 2025-26 slabs) for an individual taxpayer below 60,
including standard deduction, Section 87A rebate (with marginal
relief), and 4% health & education cess. Returns whichever regime
gives lower tax as the verdict.

VERIFIED BY HAND (worked examples, not a spreadsheet this time —
these are standard textbook slab calculations):

Example 1: Gross income 12,00,000; old-regime deductions 2,50,000
  (80C 1,50,000 + 80D 25,000 + home loan interest 75,000)
    OLD regime:
      Taxable = 12,00,000 - 50,000 (std ded) - 2,50,000 (other ded) = 9,00,000
      Tax: 0 on first 2.5L, 5% on next 2.5L = 12,500,
           20% on next 4L (5L-9L) = 80,000
      Total before cess = 92,500; cess 4% = 3,700; TOTAL = 96,200

    NEW regime:
      Taxable = 12,00,000 - 75,000 (std ded) = 11,25,000
      Tax: 0 on first 3L, 5% on next 4L (3-7L) = 20,000,
           10% on next 3L (7-10L) = 30,000,
           15% on remaining 1.25L (10-11.25L) = 18,750
      Total before cess = 68,750; cess 4% = 2,750; TOTAL = 71,500

    Winner: NEW regime (saves 24,700)

Example 2: Gross income 6,00,000; old-regime deductions 1,50,000 (80C only)
    OLD: Taxable = 6,00,000 - 50,000 - 1,50,000 = 4,00,000
         Tax: 5% on (4L - 2.5L) = 7,500. Taxable <= 5L -> 87A rebate
         wipes it out. TOTAL = 0

    NEW: Taxable = 6,00,000 - 75,000 = 5,25,000
         Tax: 5% on (5.25L - 3L) = 11,250. Taxable <= 7L -> 87A rebate
         wipes it out. TOTAL = 0

    Winner: TIE (both zero)
"""

from dataclasses import dataclass


# ==========================================================
# SLAB DEFINITIONS (FY 2024-25 / AY 2025-26, individual < 60 yrs)
# ==========================================================

OLD_REGIME_SLABS = [
    (0, 250_000, 0.00),
    (250_000, 500_000, 0.05),
    (500_000, 1_000_000, 0.20),
    (1_000_000, float("inf"), 0.30),
]
OLD_STANDARD_DEDUCTION = 50_000
OLD_REBATE_87A_LIMIT = 500_000     # taxable income threshold
OLD_REBATE_87A_MAX = 12_500        # max rebate amount

NEW_REGIME_SLABS = [
    (0, 300_000, 0.00),
    (300_000, 700_000, 0.05),
    (700_000, 1_000_000, 0.10),
    (1_000_000, 1_200_000, 0.15),
    (1_200_000, 1_500_000, 0.20),
    (1_500_000, float("inf"), 0.30),
]
NEW_STANDARD_DEDUCTION = 75_000
NEW_REBATE_87A_LIMIT = 700_000
NEW_REBATE_87A_MAX = 25_000

CESS_RATE = 0.04


# ==========================================================
# CORE SLAB MATH
# ==========================================================

def slab_tax(taxable_income, slabs):
    """Sum of tax owed by walking each slab bracket."""
    if taxable_income <= 0:
        return 0.0
    tax = 0.0
    for lower, upper, rate in slabs:
        if taxable_income > lower:
            band = min(taxable_income, upper) - lower
            tax += band * rate
        else:
            break
    return tax


def apply_87a_rebate(tax_before_rebate, taxable_income, rebate_limit, rebate_max):
    """
    Full rebate (tax -> 0) if taxable income is at/under the limit.
    Marginal relief just above the limit: caps the tax increase so it
    never exceeds the income increase past the limit -- this avoids a
    cliff where earning Re.1 more than the limit costs thousands more
    in tax than someone earning exactly the limit.
    """
    if taxable_income <= rebate_limit:
        rebate = min(tax_before_rebate, rebate_max)
        return max(0.0, tax_before_rebate - rebate)

    excess_income = taxable_income - rebate_limit
    if excess_income < tax_before_rebate:
        # marginal relief zone: tax owed is capped at the income excess
        return excess_income
    return tax_before_rebate


def compute_tax(gross_income, standard_deduction, other_deductions,
                 slabs, rebate_limit, rebate_max):
    """Full pipeline: gross -> taxable -> slab tax -> rebate -> cess -> total."""
    taxable_income = max(0.0, gross_income - standard_deduction - other_deductions)
    tax_before_rebate = slab_tax(taxable_income, slabs)
    tax_after_rebate = apply_87a_rebate(tax_before_rebate, taxable_income,
                                        rebate_limit, rebate_max)
    cess = tax_after_rebate * CESS_RATE
    total_tax = tax_after_rebate + cess
    return {
        "taxable_income": taxable_income,
        "tax_before_rebate": tax_before_rebate,
        "tax_after_rebate": tax_after_rebate,
        "cess": cess,
        "total_tax": total_tax,
        "effective_rate": (total_tax / gross_income) if gross_income > 0 else 0.0,
    }


# ==========================================================
# TOP-LEVEL: OLD vs NEW COMPARISON
# ==========================================================

@dataclass
class RegimeResult:
    regime: str
    taxable_income: float
    tax_before_rebate: float
    tax_after_rebate: float
    cess: float
    total_tax: float
    effective_rate: float


def compare_regimes(gross_income, old_regime_deductions):
    """
    gross_income: total annual income before any deductions
    old_regime_deductions: sum of everything only claimable under the
        old regime (80C, 80D, HRA exemption, Sec 24(b) home loan
        interest, 80CCD(1B) NPS, etc.) -- the new regime only ever
        gets the flat standard deduction, nothing else.
    """
    old = compute_tax(gross_income, OLD_STANDARD_DEDUCTION, old_regime_deductions,
                       OLD_REGIME_SLABS, OLD_REBATE_87A_LIMIT, OLD_REBATE_87A_MAX)
    new = compute_tax(gross_income, NEW_STANDARD_DEDUCTION, 0.0,
                       NEW_REGIME_SLABS, NEW_REBATE_87A_LIMIT, NEW_REBATE_87A_MAX)

    old_result = RegimeResult(regime="old", **old)
    new_result = RegimeResult(regime="new", **new)

    savings = abs(old_result.total_tax - new_result.total_tax)
    if new_result.total_tax < old_result.total_tax:
        winner = "new"
    elif old_result.total_tax < new_result.total_tax:
        winner = "old"
    else:
        winner = "tie"

    return {
        "old": old_result,
        "new": new_result,
        "winner": winner,
        "savings": savings,
    }


def breakeven_deduction(gross_income, tol=1.0):
    """
    Find the old-regime deduction amount at which old and new regimes
    produce equal tax -- i.e. 'you need at least this much in 80C/80D/
    home loan interest etc. for the old regime to be worth it.'
    Uses bisection since the tax functions are monotonic but slab-kinked.
    """
    lo, hi = 0.0, gross_income

    def diff(ded):
        r = compare_regimes(gross_income, ded)
        return r["old"].total_tax - r["new"].total_tax

    if diff(lo) > 0 and diff(hi) > 0:
        return None  # old regime never wins even with unlimited deductions in range
    if diff(lo) < 0:
        return 0.0  # new regime already loses at zero deductions

    # diff() is decreasing in ded: diff(lo) > 0, diff(hi) < 0 (checked above)
    for _ in range(100):
        mid = (lo + hi) / 2
        d = diff(mid)
        if abs(d) < tol:
            return mid
        if d > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ==========================================================
# VERIFICATION AGAINST HAND-WORKED EXAMPLES
# ==========================================================

if __name__ == "__main__":
    def fmt(x):
        return f"Rs {x:,.0f}"

    print("=== EXAMPLE 1: Gross 12,00,000 | Old-regime deductions 2,50,000 ===")
    r1 = compare_regimes(1_200_000, 250_000)
    print(f"OLD: taxable {fmt(r1['old'].taxable_income)} | tax {fmt(r1['old'].total_tax)}")
    print("Expected: taxable 9,00,000 | tax 96,200")
    print(f"NEW: taxable {fmt(r1['new'].taxable_income)} | tax {fmt(r1['new'].total_tax)}")
    print("Expected: taxable 11,25,000 | tax 71,500")
    print(f"Winner: {r1['winner']} | Savings: {fmt(r1['savings'])}")
    print("Expected: new | savings 24,700\n")

    print("=== EXAMPLE 2: Gross 6,00,000 | Old-regime deductions 1,50,000 ===")
    r2 = compare_regimes(600_000, 150_000)
    print(f"OLD: taxable {fmt(r2['old'].taxable_income)} | tax {fmt(r2['old'].total_tax)}")
    print("Expected: taxable 4,00,000 | tax 0 (87A rebate)")
    print(f"NEW: taxable {fmt(r2['new'].taxable_income)} | tax {fmt(r2['new'].total_tax)}")
    print("Expected: taxable 5,25,000 | tax 0 (87A rebate)")
    print(f"Winner: {r2['winner']}")
    print("Expected: tie\n")

    print("=== BREAKEVEN: Gross 12,00,000 ===")
    be = breakeven_deduction(1_200_000)
    print(f"Old-regime deductions needed for old to match new: {fmt(be)}")
    check = compare_regimes(1_200_000, be)
    print(f"At that deduction -> OLD {fmt(check['old'].total_tax)} vs NEW {fmt(check['new'].total_tax)}")