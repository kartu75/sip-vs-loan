"""
sellplan.py — Sell Plan engine (MANKART)

"I need Rs X in hand from my mutual funds. Which funds do I redeem, how many
units, and when, so tax and exit loads take the least?"

How it works:
  - Inside one folio, a redemption always uses the OLDEST units first (FIFO).
    So the only choice is HOW MANY UNITS of each fund to sell. FIFO then
    decides which lots go, and every lot has its own tax treatment, exit
    load and (for ELSS) lock-in.
  - price_plan() prices any plan exactly, lot by lot. Every number a person
    sees comes from here.
  - cheapest_plan() searches for the plan that puts exactly the target in
    hand at the lowest cost (tax + exit load), and prices "sell the same share
    of every fund" for comparison. The search is a fast heuristic; the
    self-test checks it against an exact solver (a mixed-integer program).
  - timing() looks at whether waiting (lots turning long-term, exit loads
    ending, ELSS units unlocking) or splitting the sale across 31 March (two
    years of LTCG exemption) costs less. NAVs stay at today's value: this
    never guesses where markets go.

A plan raises exactly the target. Selling extra loss-making units can cut the
tax further, but that's loss harvesting, a separate decision.

TAX RULES (sales in FY 2026-27; section numbers are the 1961 Act's, which the
Income-tax Act, 2025 carried over under new numbers)
  equity, ELSS (65%+ Indian equity)
      held > 12 months: 12.5% on gains above Rs 1.25 lakh a year (112A)
      held <= 12 months: 20% (111A)
      bought before 1 Feb 2018: cost = max(cost, min(NAV on 31 Jan 2018, sale price))
      ELSS: each purchase is locked for 3 years
  debt (65%+ debt and money market)
      bought on or after 1 Apr 2023: your slab rate, however long you held (50AA)
      bought earlier: held > 24 months 12.5% (112), else slab rate
  other (hybrid with 35-65% equity, gold, international fund of funds)
      held > 24 months 12.5% (112), else slab rate
  Short-term losses offset any gain and long-term losses only long-term
  gains, each against the most heavily taxed gains first. The Rs 1.25 lakh
  exemption applies after set-off. Surcharge on the special-rate gains is
  capped at 15%. 4% cess on everything.

SIMPLIFICATIONS (tell users)
  - slab_rate is your marginal rate; slab-taxed gains are assumed not to push
    you into a higher slab
  - your other income is assumed to use up the basic exemption and 87A rebate
  - STT (0.001%) is ignored, and so is the "first 10% of units free of exit
    load" rule some funds have
  - losses left over are not valued (in reality they carry forward 8 years)
  - one entry per folio: the same scheme in two folios is two funds
  - units are rounded up to 3 decimals, as funds allot them

VERIFIED BY HAND (sale on 3 Nov 2026, 30% slab, no surcharge, none of the
exemption used yet; re-derive these if a rule changes)

Example 1: one equity fund, NAV 100, 1% exit load within 365 days
    Lot A: 10 Jan 2024, 1,000 units, cost 50,000. Long-term, no load
           Value 1,00,000, gain 50,000 (equity LTCG)
    Lot B: 15 Jun 2026, 500 units, cost 45,000. Short-term, held 141 days -> load
           Value 50,000, load 500, gain 49,500 - 45,000 = 4,500 (equity STCG)
    Sell all 1,500 units:
           LTCG 50,000 sits inside the 1.25 L exemption -> 0
           STCG 4,500 x 20% = 900, cess 36 -> tax 936
           Cash before tax 1,49,500. In hand 1,48,564. Cost 500 + 936 = 1,436

Example 2: exemption, old debt units, a loss
    Equity fund NAV 200: 1 May 2020, 2,000 units, cost 1,00,000 -> LTCG 3,00,000
    Debt fund NAV 30, no load:
           1 Jan 2022, 10,000 units, cost 2,00,000. Before Apr 2023 and held
               > 24 months -> 12.5%, gain 1,00,000
           1 Feb 2024, 5,000 units, cost 1,60,000. From Apr 2023 -> slab rate;
               value 1,50,000, so a 10,000 short-term loss
    Sell everything:
           Nothing is taxed at the slab rate or 20%, so the loss goes against
           the 12.5% debt gain: 90,000
           Equity LTCG 3,00,000 - 1,25,000 exemption = 1,75,000
           Tax 12.5% x (1,75,000 + 90,000) = 33,125, cess 1,325 -> 34,450
           Cash before tax 8,50,000. In hand 8,15,550

Example 3: grandfathering. Equity fund NAV 300, NAV on 31 Jan 2018 = 150
    1 Jun 2015, 1,000 units, cost 1,00,000 (Rs 100 a unit)
    Cost for tax = max(100, min(150, 300)) = 150 a unit -> gain 1,50,000, not 2,00,000
    Tax 12.5% x (1,50,000 - 1,25,000) = 3,125, cess 125 -> 3,250

Example 4: cheapest plan for 2,00,000 in hand
    Fund A, equity NAV 100, 1% load within 365 days:
           15 Jan 2025, 1,500 units, cost 1,20,000 -> long-term, gain 30,000
           1 Aug 2026, 1,000 units, cost 95,000 -> short-term, with load
    Fund B, debt NAV 25: 1 Jun 2023, 8,000 units, cost 1,60,000 -> slab rate on 40,000
    Fund C, ELSS NAV 50:
           1 Mar 2022, 2,000 units, cost 60,000 -> unlocked, gain 40,000
           10 Jan 2025, 2,000 units -> locked until 10 Jan 2028
    Fund A's first lot (1,50,000) and fund C's unlocked lot (1,00,000) carry
    70,000 of long-term gains, all inside the exemption, so 2,00,000 from them
    costs nothing. The cheapest plan costs 0. Selling the same share of every
    fund would sell some of B and pay slab tax on it.

Example 5: split across 31 March. Need 6,00,000 in hand by 15 Apr 2027
    One equity fund NAV 100: 1 Jan 2020, 10,000 units, cost 5,00,000. Half of
    every rupee sold is long-term gain.
    All on one date: sell G with G - 13% x (G/2 - 1,25,000) = 6,00,000
           -> G = 6,24,331.55, cost = tax = 24,331.55
    Split: 2,50,000 by 31 Mar 2027 and 2,50,000 from 1 Apr 2027 are both
           tax-free (1,25,000 gain each, one exemption each). The last
           1,00,000 in hand needs 1,00,000 / 0.935 = 1,06,951.87 sold, taxed
           6,951.87. Cost 6,951.87, saving 17,379.68

Example 6: waiting for a lot to turn long-term. Need 1,00,000 by 31 Dec 2026
    One equity fund NAV 100, 1% load within 365 days:
           10 Dec 2025, 3,000 units, cost 2,40,000 (Rs 80 a unit)
    Today the lot is short-term with load. Per unit: 100 - 1 load = 99,
           gain 19, tax 19 x 20.8% = 3.952, in hand 95.048, cost 4.952
           Cost = 1,00,000 x 4.952 / 95.048 = 5,210
    10 Dec 2026: held 365 days, so no load, but still short-term
    11 Dec 2026: long-term; 1,000 units carry a 20,000 gain, inside the
           exemption. Cost 0. From 11 Dec 2026 the plan costs nothing
"""

import calendar
import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date, timedelta
from heapq import heapify, heappop, heappush


# ==========================================================
# RULES (sales in FY 2026-27)
# ==========================================================

EQUITY_ST_RATE = 0.20          # 111A
LT_RATE = 0.125                # 112A and 112
LTCG_EXEMPTION = 125_000       # a year, on 112A gains only
SPECIAL_SURCHARGE_CAP = 0.15   # surcharge cap on 111A / 112A / 112 gains
CESS_RATE = 0.04

EQUITY_LT_MONTHS = 12          # equity units held MORE than this are long-term
OTHER_LT_MONTHS = 24           # same for older debt, hybrid, gold, international
ELSS_LOCK_MONTHS = 36
SLAB_DEBT_FROM = date(2023, 4, 1)      # debt units bought from here: slab rate always
GRANDFATHER_BEFORE = date(2018, 2, 1)  # equity units bought before: 31 Jan 2018 NAV counts

KINDS = ("equity", "elss", "debt", "other")
EQUITY_KINDS = ("equity", "elss")

# A plan's totals travel as one list of 8 numbers, indexed by these names
GROSS, LOAD, SLAB, EQ_ST, LT, EQ_LT, ST_LOSS, LT_LOSS = range(8)
GAINS = (SLAB, EQ_ST, LT, EQ_LT)
TAX_BUCKETS = GAINS + (ST_LOSS, LT_LOSS)

UNIT_DECIMALS = 3          # funds allot units to 3 decimals
TOL = 0.005                # half a paisa
POLISH_TOP = 3             # how many of the best starting plans get polished
POLISH_MIN_STEP = 100      # smallest shift (Rs) the polish tries
WORTH_IT = 100             # timing advice only if it saves at least Rs 100
SPLIT_GRID = 6             # first look at the split in sixths of the target


# ==========================================================
# INPUTS
# ==========================================================

@dataclass
class Lot:
    bought: date
    units: float
    cost: float                       # total amount paid for these units


@dataclass
class Fund:
    name: str
    kind: str                         # "equity" | "elss" | "debt" | "other"
    nav: float                        # today's NAV
    lots: list
    exit_load: float = 0.0            # 0.01 = 1%
    exit_load_days: int = 0           # charged if redeemed within this many days
    nav_31jan2018: float | None = None  # only used for equity bought before 1 Feb 2018


@dataclass
class Payer:
    slab_rate: float = 0.30           # marginal slab rate
    surcharge: float = 0.0            # 0.10 = 10%; 0 below Rs 50 lakh income
    exemption_left: float = LTCG_EXEMPTION

    def __post_init__(self):
        # Tax per rupee of each kind of gain, surcharge and cess included
        special = (1 + min(self.surcharge, SPECIAL_SURCHARGE_CAP)) * (1 + CESS_RATE)
        self.rate = {SLAB: self.slab_rate * (1 + self.surcharge) * (1 + CESS_RATE),
                     EQ_ST: EQUITY_ST_RATE * special,
                     LT: LT_RATE * special,
                     EQ_LT: LT_RATE * special}
        # Short-term losses go against the most heavily taxed gains first;
        # 112A gains come last, since their first Rs 1.25 lakh is tax-free anyway.
        self.st_loss_order = sorted((SLAB, EQ_ST, LT), key=lambda b: -self.rate[b]) + [EQ_LT]


# ==========================================================
# DATES
# ==========================================================

def add_months(d, months):
    """Same day `months` later, clamped to the month's end (31 Jan + 1 -> 28 Feb)."""
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def fy_of(d):
    """Year the financial year starts in: 3 Nov 2026 -> 2026 (FY 2026-27)."""
    return d.year if d.month >= 4 else d.year - 1


def _changes(fund, lot):
    """Dates on which a lot's treatment changes: turning long-term, exit load ending, unlocking."""
    out = []
    if fund.kind in EQUITY_KINDS:
        out.append(add_months(lot.bought, EQUITY_LT_MONTHS) + timedelta(days=1))
    elif not (fund.kind == "debt" and lot.bought >= SLAB_DEBT_FROM):
        out.append(add_months(lot.bought, OTHER_LT_MONTHS) + timedelta(days=1))
    if fund.kind == "elss":
        out.append(add_months(lot.bought, ELSS_LOCK_MONTHS))
    if fund.exit_load > 0:
        out.append(lot.bought + timedelta(days=fund.exit_load_days))
    return out


# ==========================================================
# ONE LOT
# ==========================================================

def _bucket(kind, bought, sold_on):
    """Which kind of gain a lot makes when sold on `sold_on`."""
    if kind in EQUITY_KINDS:
        return EQ_LT if sold_on > add_months(bought, EQUITY_LT_MONTHS) else EQ_ST
    if kind == "debt" and bought >= SLAB_DEBT_FROM:
        return SLAB
    return LT if sold_on > add_months(bought, OTHER_LT_MONTHS) else SLAB


def _locked(fund, lot, sold_on):
    return fund.kind == "elss" and sold_on < add_months(lot.bought, ELSS_LOCK_MONTHS)


def _lot_totals(fund, lot, sold_on):
    """Totals for redeeming a whole lot on `sold_on`."""
    if fund.kind not in KINDS:
        raise ValueError(f"{fund.name}: kind must be one of {KINDS}")
    if lot.bought > sold_on:
        raise ValueError(f"{fund.name}: a lot is dated after the sale date")
    v = [0.0] * 8
    gross = lot.units * fund.nav
    held_days = (sold_on - lot.bought).days
    load = gross * fund.exit_load if held_days < fund.exit_load_days else 0.0
    price = (gross - load) / lot.units
    unit_cost = lot.cost / lot.units
    if (fund.kind in EQUITY_KINDS and lot.bought < GRANDFATHER_BEFORE
            and fund.nav_31jan2018 is not None):
        unit_cost = max(unit_cost, min(fund.nav_31jan2018, price))
    gain = (price - unit_cost) * lot.units

    bucket = _bucket(fund.kind, lot.bought, sold_on)
    v[GROSS], v[LOAD] = gross, load
    if gain >= 0:
        v[bucket] = gain
    else:
        v[LT_LOSS if bucket in (LT, EQ_LT) else ST_LOSS] = -gain
    return v


def _plus(a, b):
    return [x + y for x, y in zip(a, b)]


def _minus(a, b):
    return [x - y for x, y in zip(a, b)]


def _sum(vectors):
    return [sum(col) for col in zip(*vectors)] or [0.0] * 8


class _Path:
    """One fund's sellable lots in FIFO order on a sale date, with running totals."""

    def __init__(self, fund, sold_on):
        self.fund = fund
        self.lots = []              # (lot, totals for the whole lot)
        self.locked = []            # ELSS lots still inside their 3 years
        self.cum_units = [0.0]
        self.cum = [[0.0] * 8]
        for lot in sorted(fund.lots, key=lambda l: l.bought):
            # lots are in date order, so once one is locked the rest are too
            if self.locked or _locked(fund, lot, sold_on):
                self.locked.append(lot)
                continue
            v = _lot_totals(fund, lot, sold_on)
            self.lots.append((lot, v))
            self.cum_units.append(self.cum_units[-1] + lot.units)
            self.cum.append(_plus(self.cum[-1], v))
        self.units = self.cum_units[-1]

    def totals(self, units):
        """Totals for selling `units` units, oldest first."""
        if units <= 0:
            return self.cum[0]
        if units >= self.units:
            return self.cum[-1]
        i = bisect_right(self.cum_units, units) - 1
        frac = (units - self.cum_units[i]) / self.lots[i][0].units
        return [c + frac * x for c, x in zip(self.cum[i], self.lots[i][1])]


# ==========================================================
# TAX ON A WHOLE PLAN
# ==========================================================

def _set_off(v, payer):
    """
    Copy of v after losses are set off: long-term losses against long-term
    gains (112 first, it has no exemption), short-term losses against the most
    heavily taxed gains. Losses left over stay in ST_LOSS / LT_LOSS.
    """
    g = list(v)
    for loss, buckets in ((LT_LOSS, (LT, EQ_LT)), (ST_LOSS, payer.st_loss_order)):
        for b in buckets:
            used = min(g[loss], g[b])
            g[b] -= used
            g[loss] -= used
    return g


def _tax(v, payer):
    g = _set_off(v, payer)
    g[EQ_LT] = max(0.0, g[EQ_LT] - payer.exemption_left)
    return sum(g[b] * payer.rate[b] for b in GAINS)


def _cost_and_cash(v, payer):
    """(tax + exit load, cash in hand after tax) for a plan's totals."""
    tax = _tax(v, payer)
    return v[LOAD] + tax, v[GROSS] - v[LOAD] - tax


def _smallest(cash_at, lo, hi, target):
    """
    Smallest x in [lo, hi] at which cash_at(x) reaches target. Cash rises with
    x and is piecewise linear, so false position (Illinois variant) lands on
    it in a few steps.
    """
    f_lo, f_hi = cash_at(lo) - target, cash_at(hi) - target
    if f_lo >= 0:
        return lo
    side = 0
    for _ in range(100):
        x = hi - f_hi * (hi - lo) / (f_hi - f_lo)
        if not lo < x < hi:
            x = (lo + hi) / 2
        fx = cash_at(x) - target
        if 0 <= fx < 0.001:
            return x
        if fx >= 0:
            hi, f_hi = x, fx
            if side == 1:
                f_lo /= 2
            side = 1
        else:
            lo, f_lo = x, fx
            if side == -1:
                f_hi /= 2
            side = -1
        if hi - lo < 1e-9:
            break
    return hi


# ==========================================================
# THE SEARCH
# ==========================================================

def _rates(v, payer):
    """
    What one more rupee of each kind of gain costs in tax at this point in a
    plan (losses: what one more rupee of loss saves, as a negative).
    """
    g = _set_off(v, payer)
    r = [0.0] * 8
    for b in GAINS:
        r[b] = payer.rate[b]
    if g[EQ_LT] < payer.exemption_left:
        r[EQ_LT] = 0.0
    # an extra rupee of loss saves the rate of the gain it would offset next
    r[LT_LOSS] = -next((r[b] for b in (LT, EQ_LT) if g[b] > 0), 0.0)
    r[ST_LOSS] = -next((r[b] for b in payer.st_loss_order if g[b] > 0), 0.0)
    return r


def _regimes(payer):
    """
    Fixed per-rupee rates worth trying: gains taxed in full or covered by
    spare losses, the exemption used up or not, and losses worth nothing or
    the rate of each gain they could offset.
    """
    full = payer.rate
    seen, out = set(), []
    for free in ((), (LT, EQ_LT), GAINS):
        for eq_lt in (0.0, full[EQ_LT]):
            for lt_loss in (0.0, full[LT]):
                for st_loss in (0.0, full[SLAB], full[EQ_ST], full[LT]):
                    r = [0.0] * 8
                    for b in GAINS:
                        r[b] = 0.0 if b in free else full[b]
                    if EQ_LT not in free:
                        r[EQ_LT] = eq_lt
                    r[LT_LOSS], r[ST_LOSS] = -lt_loss, -st_loss
                    if tuple(r) not in seen:
                        seen.add(tuple(r))
                        out.append(r)
    return out


def _slope(a, b):
    return (b[1] - a[1]) / (b[0] - a[0])


def _hull(path, units, rates):
    """
    Corners (cash, cost, units) of the cheapest way to sell more of one fund,
    starting from `units` already sold, with tax at fixed per-rupee rates.
    FIFO means a cheap lot behind an expensive one costs the average of the
    two, which is exactly what the lower convex hull captures.
    """
    base = path.totals(units)
    points = [(0.0, 0.0, units)]
    for j in range(bisect_right(path.cum_units, units), len(path.cum_units)):
        d = _minus(path.cum[j], base)
        cost = d[LOAD] + sum(rates[b] * d[b] for b in TAX_BUCKETS)
        points.append((d[GROSS] - cost, cost, path.cum_units[j]))
    hull = [points[0]]
    for p in points[1:]:
        while len(hull) >= 2 and _slope(hull[-2], hull[-1]) >= _slope(hull[-1], p):
            hull.pop()
        hull.append(p)
    return hull


def _greedy(paths, target, payer, fixed_rates=None):
    """
    Take hull segments from all funds in order of cost per rupee in hand,
    until the target is reached. With fixed_rates, price tax at those rates
    throughout; otherwise use the rates at the current point, and rebuild
    the hulls whenever they change (say, the exemption runs out).
    """
    units = [0.0] * len(paths)
    parts = [p.cum[0] for p in paths]
    totals = [0.0] * 8
    while True:
        rates = fixed_rates or _rates(totals, payer)
        hulls = [_hull(p, units[f], rates) for f, p in enumerate(paths)]
        nxt = [1] * len(paths)
        heap = [(_slope(h[0], h[1]), f) for f, h in enumerate(hulls) if len(h) > 1]
        heapify(heap)
        rates_changed = False
        while heap:
            _, f = heappop(heap)
            p, corner = paths[f], hulls[f][nxt[f]]
            rest = _minus(totals, parts[f])
            new_part = p.totals(corner[2])
            new_totals = _plus(rest, new_part)
            if _cost_and_cash(new_totals, payer)[1] >= target - TOL:
                units[f] = _smallest(
                    lambda u: _cost_and_cash(_plus(rest, p.totals(u)), payer)[1],
                    units[f], corner[2], target)
                return units
            units[f], parts[f], totals = corner[2], new_part, new_totals
            nxt[f] += 1
            if nxt[f] < len(hulls[f]):
                heappush(heap, (_slope(hulls[f][nxt[f] - 1], hulls[f][nxt[f]]), f))
            if not fixed_rates and _rates(totals, payer) != rates:
                rates_changed = True
                break
        if not rates_changed:
            return units             # everything sellable is sold


def _polish(paths, units, target, payer):
    """
    Rates per rupee are only exact between kinks (the exemption running out
    mid-lot, say). So keep trying: sell a bit less of one fund, make the cash
    up from another, keep the change if the exact cost falls. Shifts halve
    from an eighth of the target down to Rs 100.
    """
    units = list(units)
    parts = [p.totals(u) for p, u in zip(paths, units)]
    totals = _sum(parts)
    cost = _cost_and_cash(totals, payer)[0]
    step = target / 8
    moves = 0
    while step >= POLISH_MIN_STEP and moves < 500:
        improved = True
        while improved and moves < 500:
            improved = False
            for f, pf in enumerate(paths):
                if units[f] <= 0:
                    continue
                new_f = max(0.0, units[f] - step / pf.fund.nav)
                part_f = pf.totals(new_f)
                for g, pg in enumerate(paths):
                    if g == f or units[g] >= pg.units:
                        continue
                    rest = _plus(_minus(_minus(totals, parts[f]), parts[g]), part_f)

                    def cash_at(u, rest=rest, pg=pg):
                        return _cost_and_cash(_plus(rest, pg.totals(u)), payer)[1]

                    if cash_at(pg.units) < target - TOL:
                        continue
                    new_g = _smallest(cash_at, units[g], pg.units, target)
                    new_totals = _plus(rest, pg.totals(new_g))
                    new_cost = _cost_and_cash(new_totals, payer)[0]
                    if new_cost < cost - 0.01:
                        units[f], units[g] = new_f, new_g
                        parts[f], parts[g] = part_f, pg.totals(new_g)
                        totals, cost = new_totals, new_cost
                        improved = True
                        moves += 1
                        break
        step /= 2
    return units


def _search(paths, target, payer):
    """
    Units of each fund that put `target` in hand at the lowest cost found.

    The exact problem is hard: FIFO can force you through an expensive lot to
    reach a cheap one, and a loss is only worth something if a gain is there
    for it to offset. So build plans greedily under every plausible set of
    per-rupee tax rates, price each exactly, polish the best few, and keep
    the cheapest.
    """
    def cost_of(units):
        return _cost_and_cash(_sum(p.totals(u) for p, u in zip(paths, units)), payer)[0]

    starts = {}
    for rates in [None] + _regimes(payer):
        units = _greedy(paths, target, payer, rates)
        starts[tuple(round(u, 6) for u in units)] = units
    best = sorted(starts.values(), key=cost_of)[:POLISH_TOP]
    return min((_polish(paths, u, target, payer) for u in best), key=cost_of)


# ==========================================================
# PLANS
# ==========================================================

def _round_up(units, available):
    step = 10 ** UNIT_DECIMALS
    return min(available, math.ceil(units * step - 1e-6) / step)


def _describe(paths, units, payer, sold_on, target):
    """Everything a person needs to see about one plan, priced lot by lot."""
    funds = []
    for p, u in zip(paths, units):
        if u <= 0:
            continue
        v = p.totals(u)
        funds.append({
            "name": p.fund.name,
            "units": u,
            "value": v[GROSS],
            "exit_load": v[LOAD],
            "short_term_gain": v[SLAB] + v[EQ_ST] - v[ST_LOSS],
            "long_term_gain": v[LT] + v[EQ_LT] - v[LT_LOSS],
            "lots": bisect_left(p.cum_units, u),
        })
    totals = _sum(p.totals(u) for p, u in zip(paths, units))
    cost, cash = _cost_and_cash(totals, payer)
    g = _set_off(totals, payer)
    exempt = min(g[EQ_LT], payer.exemption_left)
    return {
        "sold_on": sold_on,
        "feasible": cash >= target - TOL,
        "target": target,
        "units": list(units),         # one per fund, in the order given
        "funds": funds,
        "value": totals[GROSS],
        "exit_load": totals[LOAD],
        "tax": cost - totals[LOAD],
        "cash_in_hand": cash,
        "cost": cost,
        "tax_detail": {
            "taxed_at_slab": g[SLAB],
            "taxed_at_20": g[EQ_ST],
            "taxed_at_12_5": g[LT] + g[EQ_LT] - exempt,
            "exempt": exempt,
            "losses_left": g[ST_LOSS] + g[LT_LOSS],
        },
        "locked": [
            {"name": p.fund.name, "units": sum(l.units for l in p.locked),
             "next_unlock": add_months(p.locked[0].bought, ELSS_LOCK_MONTHS)}
            for p in paths if p.locked and p.fund.kind == "elss"
        ],
    }


def price_plan(funds, units, sold_on, payer):
    """Exact cost of selling units[i] of funds[i] on `sold_on`, oldest units first."""
    paths = [_Path(f, sold_on) for f in funds]
    return _describe(paths, units, payer, sold_on, target=0.0)


def _even_split_cost(paths, target, payer):
    """Cost of selling the same share of every fund: the plan to beat."""
    def totals_at(share):
        return _sum(p.totals(share * p.units) for p in paths)

    share = _smallest(lambda s: _cost_and_cash(totals_at(s), payer)[1], 0.0, 1.0, target)
    return _cost_and_cash(totals_at(share), payer)[0]


def cheapest_plan(funds, target, sold_on, payer):
    """
    The plan that puts `target` in hand on `sold_on` at the lowest cost found.
    If the funds can't raise that much, "feasible" is False and "max_cash"
    says how much they can.
    """
    paths = [_Path(f, sold_on) for f in funds]
    everything = [p.units for p in paths]
    max_cash = _cost_and_cash(_sum(p.cum[-1] for p in paths), payer)[1]
    if max_cash < target - TOL:
        plan = _describe(paths, everything, payer, sold_on, target)
        plan.update(feasible=False, max_cash=max_cash, even_split_cost=None)
        return plan

    units = [_round_up(u, p.units) for p, u in zip(paths, _search(paths, target, payer))]
    plan = _describe(paths, units, payer, sold_on, target)
    plan.update(max_cash=max_cash, even_split_cost=_even_split_cost(paths, target, payer))
    return plan


def _without_sold(funds, units):
    """The funds left after units[i] of funds[i] are sold, oldest first."""
    left = []
    for fund, to_go in zip(funds, units):
        lots = []
        for lot in sorted(fund.lots, key=lambda l: l.bought):
            take = min(to_go, lot.units)
            to_go -= take
            if lot.units - take > 1e-9:
                keep = (lot.units - take) / lot.units
                lots.append(Lot(lot.bought, lot.units - take, lot.cost * keep))
        left.append(Fund(fund.name, fund.kind, fund.nav, lots, fund.exit_load,
                         fund.exit_load_days, fund.nav_31jan2018))
    return left


def _ready_on(funds, units, after, until):
    """
    The first date after which every lot a plan sells is treated as it is on
    `until`: long-term, past its exit load, unlocked.
    """
    ready = after
    for fund, to_go in zip(funds, units):
        for lot in sorted(fund.lots, key=lambda l: l.bought):
            if to_go <= 1e-9:
                break
            to_go -= lot.units
            ready = max([ready] + [d for d in _changes(fund, lot) if d <= until])
    return ready


def _cheaper(a, b):
    """True if plan a is feasible and costs at least Rs 100 less than plan b."""
    if a is None or not a["feasible"]:
        return False
    return b is None or not b["feasible"] or a["cost"] < b["cost"] - WORTH_IT


def payers_from(today, slab_rate, surcharge, ltcg_exemption_used):
    """A Payer for any sale date: the exemption already used counts only in today's year."""
    def payer_on(d):
        used = ltcg_exemption_used if fy_of(d) == fy_of(today) else 0.0
        return Payer(slab_rate, surcharge, max(0.0, LTCG_EXEMPTION - used))
    return payer_on


def timing(funds, target, today, need_by, slab_rate=0.30, surcharge=0.0,
           ltcg_exemption_used=0.0):
    """
    Two ways timing can help when the money is only needed by `need_by`:
      wait:  the plan that is cheapest by need_by, on the first date when
             every unit it sells is already long-term and out of exit load
      split: sell part on 31 March and the rest on need_by, so each part gets
             its own year's LTCG exemption
    Each comes back only if it beats selling today by at least Rs 100.
    """
    payer_on = payers_from(today, slab_rate, surcharge, ltcg_exemption_used)
    now = cheapest_plan(funds, target, today, payer_on(today))
    result = {"now": now, "wait": None, "split": None}
    if need_by <= today:
        return result

    last = cheapest_plan(funds, target, need_by, payer_on(need_by))
    best = now
    if last["feasible"]:
        ready = _ready_on(funds, last["units"], today, need_by)
        # a fresh year's exemption may be part of why waiting helps
        new_year = date(fy_of(need_by), 4, 1)
        for d in sorted({ready, max(ready, new_year), need_by}):
            plan = last if d == need_by else cheapest_plan(funds, target, d, payer_on(d))
            if d > today and plan["feasible"] and plan["cost"] <= last["cost"] + WORTH_IT:
                if _cheaper(plan, now):
                    result["wait"] = best = plan
                break

    fy_end = date(fy_of(today) + 1, 3, 31)
    # a split only helps if a single sale pays tax on equity LTCG
    if need_by > fy_end and best["feasible"] and best["tax_detail"]["taxed_at_12_5"] > 0:
        split = _split(funds, target, fy_end, need_by, payer_on)
        if _cheaper(split, best):
            result["split"] = split
    return result


def _split(funds, target, first_on, second_on, payer_on):
    """
    How much cash to raise on `first_on` (the rest on `second_on`): try sixths
    of the target, then look either side of the best.
    """
    tried = {}

    def run(first_cash):
        first_cash = round(min(max(first_cash, 0.0), target), 2)
        if first_cash not in tried:
            tried[first_cash] = None
            first = cheapest_plan(funds, first_cash, first_on, payer_on(first_on))
            if first["feasible"]:
                rest = _without_sold(funds, first["units"])
                second = cheapest_plan(rest, target - first["cash_in_hand"], second_on,
                                       payer_on(second_on))
                if second["feasible"]:
                    tried[first_cash] = {"feasible": True, "first": first, "second": second,
                                         "cost": first["cost"] + second["cost"]}
        return tried[first_cash]

    def cost(first_cash):
        r = run(first_cash)
        return math.inf if r is None else r["cost"]

    step = target / SPLIT_GRID
    best = min((step * k for k in range(1, SPLIT_GRID)), key=cost)
    for _ in range(2):
        step /= 2
        best = min((best - step, best, best + step), key=cost)
    return run(best)


# ==========================================================
# VERIFICATION AGAINST HAND-WORKED EXAMPLES AND AN EXACT SOLVER
# ==========================================================

if __name__ == "__main__":
    import random
    import time

    SALE = date(2026, 11, 3)
    PAYER = Payer(slab_rate=0.30)

    def fmt(x):
        return f"Rs {x:,.2f}"

    def check(label, actual, expected, tol=0.5):
        print(f"  {label}: {fmt(actual)} (expected {fmt(expected)}) "
              f"{'OK' if abs(actual - expected) < tol else 'FAIL'}")

    print("=== EXAMPLE 1: long-term and short-term lots, exit load ===")
    fund = Fund("Equity", "equity", 100, [Lot(date(2024, 1, 10), 1000, 50_000),
                                          Lot(date(2026, 6, 15), 500, 45_000)],
                exit_load=0.01, exit_load_days=365)
    r = price_plan([fund], [1500], SALE, PAYER)
    check("Exit load", r["exit_load"], 500)
    check("Tax", r["tax"], 936)
    check("In hand", r["cash_in_hand"], 148_564)
    check("Cost", r["cost"], 1_436)
    print()

    print("=== EXAMPLE 2: exemption, old debt units, a loss ===")
    eq = Fund("Equity", "equity", 200, [Lot(date(2020, 5, 1), 2000, 100_000)])
    debt = Fund("Debt", "debt", 30, [Lot(date(2022, 1, 1), 10_000, 200_000),
                                     Lot(date(2024, 2, 1), 5_000, 160_000)])
    r = price_plan([eq, debt], [2000, 15_000], SALE, PAYER)
    check("Taxed at 12.5%", r["tax_detail"]["taxed_at_12_5"], 265_000)
    check("Tax", r["tax"], 34_450)
    check("In hand", r["cash_in_hand"], 815_550)
    print()

    print("=== EXAMPLE 3: grandfathering ===")
    old = Fund("Old equity", "equity", 300, [Lot(date(2015, 6, 1), 1000, 100_000)],
               nav_31jan2018=150)
    r = price_plan([old], [1000], SALE, PAYER)
    check("Long-term gain", r["funds"][0]["long_term_gain"], 150_000)
    check("Tax", r["tax"], 3_250)
    print()

    print("=== EXAMPLE 4: cheapest plan for 2,00,000 in hand ===")
    fund_a = Fund("A", "equity", 100, [Lot(date(2025, 1, 15), 1500, 120_000),
                                       Lot(date(2026, 8, 1), 1000, 95_000)],
                  exit_load=0.01, exit_load_days=365)
    fund_b = Fund("B", "debt", 25, [Lot(date(2023, 6, 1), 8000, 160_000)])
    fund_c = Fund("C", "elss", 50, [Lot(date(2022, 3, 1), 2000, 60_000),
                                    Lot(date(2025, 1, 10), 2000, 70_000)])
    r = cheapest_plan([fund_a, fund_b, fund_c], 200_000, SALE, PAYER)
    check("Cost", r["cost"], 0)
    check("In hand", r["cash_in_hand"], 200_000, tol=1)
    print(f"  Sells: {', '.join(f['name'] + ' ' + format(f['units'], ',.3f') for f in r['funds'])}"
          f" {'OK' if {f['name'] for f in r['funds']} <= {'A', 'C'} else 'FAIL'}")
    print(f"  Selling evenly would cost {fmt(r['even_split_cost'])} "
          f"{'OK' if r['even_split_cost'] > 0 else 'FAIL'}")
    print(f"  Locked: {r['locked']}")
    print()

    print("=== EXAMPLE 5: split across 31 March ===")
    one = Fund("Equity", "equity", 100, [Lot(date(2020, 1, 1), 10_000, 500_000)])
    r = timing([one], 600_000, SALE, need_by=date(2027, 4, 15))
    check("One date, cost", r["now"]["cost"], 24_331.55, tol=1)
    check("Split, cost", r["split"]["cost"], 6_951.87, tol=1)
    print(f"  First part {fmt(r['split']['first']['cash_in_hand'])} on "
          f"{r['split']['first']['sold_on']}, rest on {r['split']['second']['sold_on']}")
    print()

    print("=== EXAMPLE 6: waiting for a lot to turn long-term ===")
    young = Fund("Equity", "equity", 100, [Lot(date(2025, 12, 10), 3000, 240_000)],
                 exit_load=0.01, exit_load_days=365)
    r = timing([young], 100_000, SALE, need_by=date(2026, 12, 31))
    check("Today, cost", r["now"]["cost"], 5_210, tol=1)
    check("Waiting, cost", r["wait"]["cost"], 0)
    print(f"  Wait until: {r['wait']['sold_on']} (expected 2026-12-11)")
    print()

    # ------------------------------------------------------
    # The exact referee: the same problem as a mixed-integer linear program.
    # Variables, in lakhs: y[i] share of lot i sold; full[i] = 1 once lot i is
    # fully sold, and only then may the fund's next lot be touched (FIFO);
    # offsets of each loss against each gain; gains left to tax.
    # Minimise exit loads + tax, with cash in hand exactly the target.
    # ------------------------------------------------------
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_matrix

    OFFSETS = [(LT_LOSS, LT), (LT_LOSS, EQ_LT),
               (ST_LOSS, SLAB), (ST_LOSS, EQ_ST), (ST_LOSS, LT), (ST_LOSS, EQ_LT)]

    def exact_cost(funds, target, sold_on, payer):
        lots = [(f, v) for f, fund in enumerate(funds) for _, v in _Path(fund, sold_on).lots]
        n = len(lots)
        links = [i for i in range(n - 1) if lots[i][0] == lots[i + 1][0]]
        off0 = n + len(links)
        taxed0 = off0 + len(OFFSETS)
        n_vars = taxed0 + len(GAINS)
        c = np.zeros(n_vars)
        upper = np.full(n_vars, np.inf)
        upper[:off0] = 1.0
        integrality = np.zeros(n_vars)
        integrality[n:off0] = 1
        rows, cols, vals, lo, hi = [], [], [], [], []

        def add(coeffs, low, high):
            for col, val in coeffs.items():
                rows.append(len(lo))
                cols.append(col)
                vals.append(val)
            lo.append(low)
            hi.append(high)

        for k, i in enumerate(links):
            add({i + 1: 1.0, n + k: -1.0}, -np.inf, 0.0)
            add({n + k: 1.0, i: -1.0}, -np.inf, 0.0)
        for loss in (LT_LOSS, ST_LOSS):
            row = {off0 + k: 1.0 for k, (l, _) in enumerate(OFFSETS) if l == loss}
            row.update({i: -v[loss] / 1e5 for i, (_, v) in enumerate(lots) if v[loss]})
            add(row, -np.inf, 0.0)
        cash = {}
        for j, b in enumerate(GAINS):
            row = {off0 + k: -1.0 for k, (_, g) in enumerate(OFFSETS) if g == b}
            row[taxed0 + j] = -1.0
            row.update({i: v[b] / 1e5 for i, (_, v) in enumerate(lots) if v[b]})
            add(row, -np.inf, payer.exemption_left / 1e5 if b == EQ_LT else 0.0)
            c[taxed0 + j] = payer.rate[b]
            cash[taxed0 + j] = -payer.rate[b]
        for i, (_, v) in enumerate(lots):
            c[i] = v[LOAD] / 1e5
            cash[i] = (v[GROSS] - v[LOAD]) / 1e5
        add(cash, target / 1e5, target / 1e5)
        res = milp(c, integrality=integrality, bounds=Bounds(np.zeros(n_vars), upper),
                   constraints=LinearConstraint(coo_matrix((vals, (rows, cols)),
                                                           shape=(len(lo), n_vars)), lo, hi),
                   options={"time_limit": 60, "mip_rel_gap": 1e-9})
        return res.fun * 1e5

    def realistic_fund(rng, i):
        """Monthly SIP into a fund whose NAV followed a random walk."""
        kind = rng.choice(KINDS)
        drift, vol = {"equity": (0.010, 0.05), "elss": (0.010, 0.05),
                      "debt": (0.0055, 0.004), "other": (0.008, 0.03)}[kind]
        months = rng.randint(3, 12)
        start = SALE - timedelta(days=30 * rng.randint(months, 90))
        nav, lots = rng.uniform(20, 200), []
        for m in range(months):
            nav *= math.exp(rng.gauss(drift, vol))
            amount = rng.choice([5_000, 10_000, 25_000])
            lots.append(Lot(start + timedelta(days=30 * m), amount / nav, amount))
        nav *= math.exp(rng.gauss(drift * 6, vol * 2.4))
        return Fund(f"F{i}", kind, nav, lots, exit_load=0.01 if kind == "equity" else 0,
                    exit_load_days=365)

    def adversarial_fund(rng, i):
        """A few lots with cost bases all over the place: lots of losses."""
        kind = rng.choice(KINDS)
        nav = rng.uniform(20, 200)
        lots = []
        for _ in range(rng.randint(1, 4)):
            units = rng.uniform(100, 3000)
            lots.append(Lot(SALE - timedelta(days=rng.randint(30, 3200)), units,
                            units * nav * rng.uniform(0.5, 1.4)))
        return Fund(f"F{i}", kind, nav, lots, exit_load=rng.choice([0, 0.01]),
                    exit_load_days=365, nav_31jan2018=nav * rng.uniform(0.3, 0.9))

    print("=== SEARCH vs EXACT SOLVER ===")
    rng = random.Random(11)
    for label, maker, n_funds, cases in (("realistic SIP portfolios", realistic_fund, 5, 60),
                                         ("adversarial, loss-heavy", adversarial_fund, 3, 60)):
        gaps = []
        for _ in range(cases):
            funds = [maker(rng, i) for i in range(n_funds)]
            payer = Payer(slab_rate=rng.choice([0.05, 0.2, 0.3]),
                          surcharge=rng.choice([0, 0, 0.1, 0.25]),
                          exemption_left=rng.choice([125_000, 125_000, 50_000, 0]))
            paths = [_Path(f, SALE) for f in funds]
            target = _cost_and_cash(_sum(p.cum[-1] for p in paths), payer)[1] * rng.uniform(0.1, 0.95)
            if target <= 0:
                continue
            gaps.append(cheapest_plan(funds, target, SALE, payer)["cost"]
                        - exact_cost(funds, target, SALE, payer))
        within = sum(g <= 2 for g in gaps)
        print(f"  {label}: {within}/{len(gaps)} within Rs 2 of exact; "
              f"worst {fmt(max(gaps))}, average {fmt(sum(gaps) / len(gaps))}")
    print()

    print("=== SPEED: 8 funds x 48 monthly lots, need by next April ===")
    funds = []
    for i in range(8):
        nav = rng.uniform(30, 300)
        kind = ["equity", "equity", "equity", "elss", "debt", "other", "equity", "debt"][i]
        lots = []
        for m in range(48):
            lot_nav = nav * (0.6 + 0.5 * m / 48) * rng.uniform(0.9, 1.1)
            lots.append(Lot(add_months(date(2022, 11, 5), m), 10_000 / lot_nav, 10_000))
        funds.append(Fund(f"Fund {i}", kind, nav, lots, exit_load=0.01 if kind == "equity" else 0,
                          exit_load_days=365))
    start = time.perf_counter()
    plan = cheapest_plan(funds, 1_500_000, SALE, PAYER)
    mid = time.perf_counter()
    r = timing(funds, 1_500_000, SALE, need_by=date(2027, 4, 30))
    end = time.perf_counter()
    print(f"  today {fmt(plan['cost'])} in {mid - start:.2f} s; timing: wait "
          f"{fmt(r['wait']['cost']) if r['wait'] else '-'}, split "
          f"{fmt(r['split']['cost']) if r['split'] else '-'} in {end - mid:.2f} s")
