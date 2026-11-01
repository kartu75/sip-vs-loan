"""
tax.py — Old vs New Tax Regime decision engine (Module 5, MANKART)

Computes income tax liability under both the Old and New regimes
(FY 2026-27 / AY 2027-28 slabs; Budget 2026 left the FY 2025-26 rates
unchanged) for a resident individual below 60, including standard
deduction, Section 87A rebate, surcharge above Rs 50 lakh and 4% health &
education cess. Returns whichever regime gives lower tax as the verdict.

Rules worth remembering:
  - 87A marginal relief exists ONLY in the new regime. In the old regime,
    crossing Rs 5 lakh of taxable income brings back the full slab tax.
  - Surcharge has its own marginal relief in both regimes, and the new
    regime caps surcharge at 25% (old goes to 37% above Rs 5 crore).

VERIFIED BY HAND (worked examples; re-derive these if a rule changes):

Example 1: Gross 12,00,000; old-regime deductions 2,50,000
    OLD: Taxable = 12,00,000 - 50,000 - 2,50,000 = 9,00,000
         Tax: 5% of 2.5L = 12,500 + 20% of 4L = 80,000 -> 92,500
         Cess 3,700. TOTAL = 96,200
    NEW: Taxable = 12,00,000 - 75,000 = 11,25,000
         Tax: 5% of 4L = 20,000 + 10% of 3.25L = 32,500 -> 52,500
         Taxable <= 12L -> 87A rebate wipes it out. TOTAL = 0
    Winner: NEW (saves 96,200)

Example 2: Gross 6,00,000; deductions 1,50,000
    OLD: Taxable 4,00,000, tax 7,500, rebate -> 0
    NEW: Taxable 5,25,000, tax 6,250, rebate -> 0
    Winner: TIE

Example 3: Gross 16,00,000; deductions 4,00,000
    OLD: Taxable 11,50,000. Tax 1,12,500 + 30% of 1.5L = 1,57,500
         Cess 6,300. TOTAL = 1,63,800
    NEW: Taxable 15,25,000. Tax 20,000 + 40,000 + 15% of 3.25L = 1,08,750
         Cess 4,350. TOTAL = 1,13,100
    Winner: NEW (saves 50,700)

Example 4 (new regime marginal relief): Gross 13,25,000
    NEW: Taxable 12,50,000. Slab tax 60,000 + 7,500 = 67,500
         Income above 12L is 50,000, so tax is capped at 50,000
         Cess 2,000. TOTAL = 52,000

Example 5 (old regime has NO marginal relief): Gross 5,60,000; no deductions
    OLD: Taxable 5,10,000. Tax 12,500 + 2,000 = 14,500 (no rebate, no cap)
         Cess 580. TOTAL = 15,080

Example 6 (surcharge): Gross 60,75,000
    NEW: Taxable 60,00,000. Tax 3,00,000 + 30% of 36L = 13,80,000
         Surcharge 10% = 1,38,000. Cess 4% of 15,18,000 = 60,720
         TOTAL = 15,78,720

Example 7 (surcharge marginal relief): Gross 51,25,000
    NEW: Taxable 50,50,000. Tax 10,95,000; +10% would be 12,04,500
         Tax at exactly 50L = 10,80,000, plus the 50,000 above it = 11,30,000
         So surcharge is only 35,000. Cess 45,200. TOTAL = 11,75,200

Example 8 (top surcharge): taxable 6,00,00,000 in both regimes
    OLD: Tax 1,78,12,500; 37% = 65,90,625; cess 9,76,125. TOTAL = 2,53,79,250
    NEW: Tax 1,75,80,000; 25% = 43,95,000; cess 8,79,000. TOTAL = 2,28,54,000
"""

from dataclasses import dataclass


# ==========================================================
# SLAB DEFINITIONS (FY 2026-27 / AY 2027-28, individual < 60 yrs)
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
    (0, 400_000, 0.00),
    (400_000, 800_000, 0.05),
    (800_000, 1_200_000, 0.10),
    (1_200_000, 1_600_000, 0.15),
    (1_600_000, 2_000_000, 0.20),
    (2_000_000, 2_400_000, 0.25),
    (2_400_000, float("inf"), 0.30),
]
NEW_STANDARD_DEDUCTION = 75_000
NEW_REBATE_87A_LIMIT = 1_200_000
NEW_REBATE_87A_MAX = 60_000

# (income above this, surcharge rate on the tax)
OLD_SURCHARGE_BANDS = [
    (5_000_000, 0.10),
    (10_000_000, 0.15),
    (20_000_000, 0.25),
    (50_000_000, 0.37),
]
NEW_SURCHARGE_BANDS = [
    (5_000_000, 0.10),
    (10_000_000, 0.15),
    (20_000_000, 0.25),
]

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


def apply_87a_rebate(tax_before_rebate, taxable_income, rebate_limit, rebate_max,
                     marginal_relief):
    """
    Full rebate (tax -> 0) if taxable income is at/under the limit.
    Marginal relief (new regime only) applies just above the limit: caps the
    tax so it never exceeds the income past the limit -- this avoids a cliff
    where earning Re.1 more than the limit costs thousands more in tax.
    """
    if taxable_income <= rebate_limit:
        rebate = min(tax_before_rebate, rebate_max)
        return max(0.0, tax_before_rebate - rebate)

    if marginal_relief:
        excess_income = taxable_income - rebate_limit
        if excess_income < tax_before_rebate:
            return excess_income
    return tax_before_rebate


def surcharge_on(tax, taxable_income, slabs, bands):
    """
    Surcharge at the rate for this income's band, with marginal relief: tax
    plus surcharge can't exceed the tax plus surcharge at the band's threshold
    by more than the income earned above that threshold.
    """
    rate, threshold, rate_below = 0.0, None, 0.0
    for band_start, band_rate in bands:
        if taxable_income > band_start:
            rate_below = rate
            rate, threshold = band_rate, band_start
    if threshold is None:
        return 0.0

    with_surcharge = tax * (1 + rate)
    at_threshold = slab_tax(threshold, slabs) * (1 + rate_below)
    capped = at_threshold + (taxable_income - threshold)
    return min(with_surcharge, capped) - tax


def compute_tax(gross_income, standard_deduction, other_deductions,
                 slabs, rebate_limit, rebate_max, marginal_relief, surcharge_bands):
    """Full pipeline: gross -> taxable -> slab tax -> rebate -> surcharge -> cess -> total."""
    taxable_income = max(0.0, gross_income - standard_deduction - other_deductions)
    tax_before_rebate = slab_tax(taxable_income, slabs)
    tax_after_rebate = apply_87a_rebate(tax_before_rebate, taxable_income,
                                        rebate_limit, rebate_max, marginal_relief)
    surcharge = surcharge_on(tax_after_rebate, taxable_income, slabs, surcharge_bands)
    cess = (tax_after_rebate + surcharge) * CESS_RATE
    total_tax = tax_after_rebate + surcharge + cess
    return {
        "taxable_income": taxable_income,
        "tax_before_rebate": tax_before_rebate,
        "tax_after_rebate": tax_after_rebate,
        "surcharge": surcharge,
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
    surcharge: float
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
                       OLD_REGIME_SLABS, OLD_REBATE_87A_LIMIT, OLD_REBATE_87A_MAX,
                       marginal_relief=False, surcharge_bands=OLD_SURCHARGE_BANDS)
    new = compute_tax(gross_income, NEW_STANDARD_DEDUCTION, 0.0,
                       NEW_REGIME_SLABS, NEW_REBATE_87A_LIMIT, NEW_REBATE_87A_MAX,
                       marginal_relief=True, surcharge_bands=NEW_SURCHARGE_BANDS)

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

    def check(label, actual, expected):
        print(f"  {label}: {fmt(actual)} (expected {fmt(expected)}) "
              f"{'OK' if abs(actual - expected) < 0.5 else 'FAIL'}")

    print("=== EXAMPLE 1: Gross 12,00,000 | Deductions 2,50,000 ===")
    r = compare_regimes(1_200_000, 250_000)
    check("OLD taxable", r["old"].taxable_income, 900_000)
    check("OLD total", r["old"].total_tax, 96_200)
    check("NEW taxable", r["new"].taxable_income, 1_125_000)
    check("NEW total", r["new"].total_tax, 0)
    check("Savings", r["savings"], 96_200)
    print(f"  Winner: {r['winner']} (expected new)\n")

    print("=== EXAMPLE 2: Gross 6,00,000 | Deductions 1,50,000 ===")
    r = compare_regimes(600_000, 150_000)
    check("OLD total", r["old"].total_tax, 0)
    check("NEW total", r["new"].total_tax, 0)
    print(f"  Winner: {r['winner']} (expected tie)\n")

    print("=== EXAMPLE 3: Gross 16,00,000 | Deductions 4,00,000 ===")
    r = compare_regimes(1_600_000, 400_000)
    check("OLD total", r["old"].total_tax, 163_800)
    check("NEW total", r["new"].total_tax, 113_100)
    check("Savings", r["savings"], 50_700)
    print(f"  Winner: {r['winner']} (expected new)\n")

    print("=== EXAMPLE 4: New regime marginal relief, Gross 13,25,000 ===")
    r = compare_regimes(1_325_000, 0)
    check("NEW tax after relief", r["new"].tax_after_rebate, 50_000)
    check("NEW total", r["new"].total_tax, 52_000)
    print()

    print("=== EXAMPLE 5: Old regime has no marginal relief, Gross 5,60,000 ===")
    r = compare_regimes(560_000, 0)
    check("OLD tax after rebate", r["old"].tax_after_rebate, 14_500)
    check("OLD total", r["old"].total_tax, 15_080)
    print()

    print("=== EXAMPLE 6: Surcharge, Gross 60,75,000 ===")
    r = compare_regimes(6_075_000, 0)
    check("NEW surcharge", r["new"].surcharge, 138_000)
    check("NEW total", r["new"].total_tax, 1_578_720)
    print()

    print("=== EXAMPLE 7: Surcharge marginal relief, Gross 51,25,000 ===")
    r = compare_regimes(5_125_000, 0)
    check("NEW surcharge", r["new"].surcharge, 35_000)
    check("NEW total", r["new"].total_tax, 1_175_200)
    print()

    print("=== EXAMPLE 8: Top surcharge, taxable 6 crore in both regimes ===")
    check("OLD total", compare_regimes(60_050_000, 0)["old"].total_tax, 25_379_250)
    check("NEW total", compare_regimes(60_075_000, 0)["new"].total_tax, 22_854_000)
    print()

    print("=== BREAKEVEN: Gross 16,00,000 ===")
    be = breakeven_deduction(1_600_000)
    print(f"  Old-regime deductions needed for old to match new: {fmt(be)}")
    check_r = compare_regimes(1_600_000, be)
    print(f"  At that deduction -> OLD {fmt(check_r['old'].total_tax)} vs NEW {fmt(check_r['new'].total_tax)}")
