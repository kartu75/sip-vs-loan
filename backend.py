"""
backend.py — FastAPI backend for the SIP vs Loan tool
=====================================================
Exposes the verified model.py engine (and the explain.py LLM layer)
as an API that a React frontend can call.

Run:   uvicorn backend:app --reload
Test:  http://127.0.0.1:8000/docs
"""

import os
from datetime import date
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from model import (compare, find_optimal_split, find_breakevens,
                   monte_carlo, evaluate_split)
from explain import explain_decision, facts_from_results
from rentbuy import rent_vs_buy
from prepay import compare_prepay_vs_invest
from tax import compare_regimes, breakeven_deduction
from sellplan import Fund, Lot, cheapest_plan, timing, payers_from

app = FastAPI(title="SIP vs Loan API", version="1.0")

# ----------------------------------------------------------
# CORS — lets your React frontend (running on a different port)
# call this backend. Without this, the browser blocks the request.
# Only the sites in ALLOWED_ORIGINS (comma-separated) get through.
# Not set = local development only, so forgetting it stays locked down.
# ----------------------------------------------------------
ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# tax constants shared by several endpoints (kept out of user input)
TAX = dict(ltcg_exemption=125_000, ltcg_rate=0.125,
           sec_24b_limit=200_000, sec_80c_limit=150_000)


# ==========================================================
# INPUT SHAPES  (Pydantic models = the contract for each POST)
# ==========================================================

# limits keep one oversized request from tying up the server
MAX_YEARS = 60
MAX_LOAN_YEARS = 50
MAX_SIMS = 5000


class CalcInput(BaseModel):
    corpus: float
    invested: float
    cash_need: float
    monthly_sip: float
    loan_tenure: int = Field(ge=1, le=MAX_LOAN_YEARS)
    loan_rate: float
    equity_return: float
    tax_slab: float
    horizon: int = Field(default=15, ge=1, le=MAX_YEARS)
    regime: str = "old"           # "old" or "new"
    stepup_rate: float = 0.0      # 0.10 = SIP grows 10%/yr
    reinvest_emi: bool = False    # fair-mode toggle


class MonteCarloInput(BaseModel):
    corpus: float
    invested: float
    cash_need: float
    monthly_sip: float
    loan_tenure: int = Field(ge=1, le=MAX_LOAN_YEARS)
    loan_rate: float
    equity_return: float          # used as the mean return
    tax_slab: float
    horizon: int = Field(default=15, ge=1, le=MAX_YEARS)
    regime: str = "old"
    volatility: float = 0.18
    n_sims: int = Field(default=2000, ge=1, le=MAX_SIMS)
    stepup_rate: float = 0.0
    reinvest_emi: bool = False


class RentBuyInput(BaseModel):
    property_price: float
    down_payment_pct: float       # 0.20 = 20%
    loan_rate: float
    loan_tenure: int = Field(ge=1, le=MAX_LOAN_YEARS)
    monthly_rent: float
    rent_growth: float            # 0.05 = 5%/yr
    property_appreciation: float  # 0.07 = 7%/yr
    equity_return: float
    horizon: int = Field(default=15, ge=1, le=MAX_YEARS)


class PrepayInput(BaseModel):
    principal: float               # outstanding loan amount
    annual_rate: float             # loan interest rate, e.g. 0.09
    tenure_months: int = Field(ge=1, le=MAX_LOAN_YEARS * 12)  # remaining tenure in months
    surplus: float                 # one-time lump sum available
    tax_slab: float                # e.g. 0.30
    sec24b_cap: float = 200_000    # annual interest deduction cap
    equity_return: float = 0.12    # assumed investment return


class TaxRegimeInput(BaseModel):
    gross_income: float             # total annual income before deductions
    old_regime_deductions: float = 0.0   # 80C + 80D + HRA + Sec24b + NPS etc.


MAX_FUNDS = 30
MAX_LOTS = 600                      # across all funds


class LotInput(BaseModel):
    bought: date
    units: float = Field(gt=0)
    cost: float = Field(ge=0)        # total amount paid for these units


class FundInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: Literal["equity", "elss", "debt", "other"]
    nav: float = Field(gt=0)                        # today's NAV
    exit_load: float = Field(default=0.0, ge=0, le=0.1)        # 0.01 = 1%
    exit_load_days: int = Field(default=0, ge=0, le=3650)
    nav_31jan2018: float | None = Field(default=None, gt=0)    # equity bought before Feb 2018
    lots: list[LotInput] = Field(min_length=1)


class SellPlanInput(BaseModel):
    target: float = Field(gt=0)                     # cash needed in hand
    funds: list[FundInput] = Field(min_length=1, max_length=MAX_FUNDS)
    sell_on: date                                   # today, in the person's time zone
    need_by: date | None = None                     # only used by /sell-plan/timing
    slab_rate: float = Field(default=0.30, ge=0, le=0.30)
    surcharge: float = Field(default=0.0, ge=0, le=0.37)
    ltcg_exemption_used: float = Field(default=0.0, ge=0)


# ==========================================================
# ENDPOINTS
# ==========================================================

@app.get("/")
def home():
    """Health check — confirms the API is alive."""
    return {"message": "SIP vs Loan API is running"}


@app.post("/calculate")
def calculate(data: CalcInput):
    """Core comparison: redeem vs loan (both regimes) at the chosen horizon."""
    common = dict(
        corpus=data.corpus, invested=data.invested, cash_need=data.cash_need,
        monthly_sip=data.monthly_sip, loan_tenure=data.loan_tenure,
        loan_rate=data.loan_rate, equity_return=data.equity_return,
        tax_slab=data.tax_slab, horizons=(data.horizon,),
        stepup_rate=data.stepup_rate, reinvest_emi=data.reinvest_emi,
    )
    results = compare(**common)
    redeem = results["redeem"][data.horizon]
    loan   = results[f"loan_{data.regime}"][data.horizon]
    return {
        "emi": results["emi"],
        "redeem_wealth": redeem,
        "loan_wealth": loan,
        "gap": abs(loan - redeem),
        "winner": "loan" if loan > redeem else "redeem",
        "redeem_details": {
            "ltcg_tax": results["redeem_details"]["ltcg_tax"],
            "shortfall_borrowed": results["redeem_details"]["loan_amount"],
        },
    }


@app.post("/optimal-split")
def optimal_split(data: CalcInput):
    """Best redeem/borrow mix at the chosen horizon, plus the full curve."""
    best_frac, best_wealth, curve = find_optimal_split(
        corpus=data.corpus, invested=data.invested, cash_need=data.cash_need,
        monthly_sip=data.monthly_sip, loan_tenure=data.loan_tenure,
        loan_rate=data.loan_rate, equity_return=data.equity_return,
        tax_slab=data.tax_slab, regime=data.regime,
        target_horizon=data.horizon,
        stepup_rate=data.stepup_rate, reinvest_emi=data.reinvest_emi,
    )
    return {
        "best_redeem_pct": round(best_frac * 100, 1),
        "best_borrow_pct": round((1 - best_frac) * 100, 1),
        "best_wealth": best_wealth,
        "curve": [{"redeem_pct": round(f * 100), "wealth": w} for f, w in curve],
    }


@app.post("/breakeven")
def breakeven(data: CalcInput):
    """The equity-return and loan-rate values where the winner flips."""
    be = find_breakevens(
        corpus=data.corpus, invested=data.invested, cash_need=data.cash_need,
        monthly_sip=data.monthly_sip, loan_tenure=data.loan_tenure,
        loan_rate=data.loan_rate, equity_return=data.equity_return,
        tax_slab=data.tax_slab, regime=data.regime, horizon=data.horizon,
        stepup_rate=data.stepup_rate, reinvest_emi=data.reinvest_emi,
    )
    eq, lr = be["equity_breakeven"], be["loan_breakeven"]
    return {
        "equity_breakeven_pct": round(eq * 100, 2) if eq is not None else None,
        "loan_breakeven_pct":   round(lr * 100, 2) if lr is not None else None,
    }


@app.post("/montecarlo")
def montecarlo(data: MonteCarloInput):
    """Run the simulation: how often does the loan win across random markets?"""
    mc = monte_carlo(
        corpus=data.corpus, invested=data.invested, cash_need=data.cash_need,
        monthly_sip=data.monthly_sip, loan_tenure=data.loan_tenure,
        loan_rate=data.loan_rate, tax_slab=data.tax_slab, regime=data.regime,
        horizon=data.horizon, mean_return=data.equity_return,
        volatility=data.volatility, n_sims=data.n_sims,
        stepup_rate=data.stepup_rate, reinvest_emi=data.reinvest_emi,
    )
    return {
        "loan_win_prob_pct": round(mc["loan_win_prob"] * 100, 1),
        "n_sims": mc["n_sims"],
        "loan":   {"p10": mc["loan_p10"], "p50": mc["loan_p50"], "p90": mc["loan_p90"]},
        "redeem": {"p10": mc["redeem_p10"], "p50": mc["redeem_p50"], "p90": mc["redeem_p90"]},
    }


@app.post("/explain")
def explain(data: MonteCarloInput):
    """Plain-English explanation from the LLM, grounded in the computed numbers."""
    # need the comparison numbers + a monte carlo win prob for the facts
    results = compare(
        corpus=data.corpus, invested=data.invested, cash_need=data.cash_need,
        monthly_sip=data.monthly_sip, loan_tenure=data.loan_tenure,
        loan_rate=data.loan_rate, equity_return=data.equity_return,
        tax_slab=data.tax_slab, horizons=(data.horizon,),
        stepup_rate=data.stepup_rate, reinvest_emi=data.reinvest_emi,
    )
    mc = monte_carlo(
        corpus=data.corpus, invested=data.invested, cash_need=data.cash_need,
        monthly_sip=data.monthly_sip, loan_tenure=data.loan_tenure,
        loan_rate=data.loan_rate, tax_slab=data.tax_slab, regime=data.regime,
        horizon=data.horizon, mean_return=data.equity_return,
        volatility=data.volatility, n_sims=data.n_sims,
        stepup_rate=data.stepup_rate, reinvest_emi=data.reinvest_emi,
    )
    facts = facts_from_results(results, mc, data.horizon, data.regime,
                               data.equity_return, data.loan_rate)
    return {"explanation": explain_decision(facts)}


@app.post("/rent-vs-buy")
def rent_vs_buy_endpoint(data: RentBuyInput):
    """Rent (and invest) vs Buy (with a loan). Returns wealth + monthly cost."""
    r = rent_vs_buy(
        property_price=data.property_price,
        down_payment_pct=data.down_payment_pct,
        loan_rate=data.loan_rate, loan_tenure=data.loan_tenure,
        monthly_rent=data.monthly_rent, rent_growth=data.rent_growth,
        property_appreciation=data.property_appreciation,
        equity_return=data.equity_return, horizons=(data.horizon,),
    )
    y = r["years"][data.horizon]
    winner = "buy" if y["buy_wealth_hold"] > y["rent_wealth"] else "rent"
    return {
        "emi": r["emi"],
        "down_payment": r["down_payment"],
        "loan_amount": r["loan_amount"],
        "rent_wealth": y["rent_wealth"],
        "buy_wealth_sell": y["buy_wealth_sell"],
        "buy_wealth_hold": y["buy_wealth_hold"],
        "house_value": y["house_value"],
        "outstanding_loan": y["outstanding_loan"],
        "monthly_rent_at_year": y["monthly_rent_at_year"],
        "monthly_emi": y["monthly_emi"],
        "winner": winner,
    }


@app.post("/prepay-vs-invest")
def prepay_vs_invest_endpoint(data: PrepayInput):
    """Prepay loan (reduced EMI or reduced tenure) vs invest the surplus instead."""
    r = compare_prepay_vs_invest(
        principal=data.principal,
        annual_rate=data.annual_rate,
        tenure_months=data.tenure_months,
        surplus=data.surplus,
        tax_slab=data.tax_slab,
        sec24b_cap=data.sec24b_cap,
        equity_return=data.equity_return,
    )
    b = r["baseline"]
    o1 = r["option1_reduced_emi"]
    o2 = r["option2_reduced_tenure"]
    return {
        "baseline": {
            "emi": b["emi"],
            "tenure_months": b["tenure_months"],
            "total_interest": b["total_interest"],
        },
        "option1_reduced_emi": {
            "monthly_payment": o1.monthly_payment,
            "tenure_months": o1.tenure_months,
            "total_interest": o1.total_interest,
            "interest_saved": o1.interest_saved,
            "tax_deduction_lost": o1.tax_deduction_lost,
            "effective_benefit": o1.effective_benefit,
        },
        "option2_reduced_tenure": {
            "monthly_payment": o2.monthly_payment,
            "tenure_months": o2.tenure_months,
            "total_interest": o2.total_interest,
            "interest_saved": o2.interest_saved,
            "tax_deduction_lost": o2.tax_deduction_lost,
            "effective_benefit": o2.effective_benefit,
        },
        "invest_terminal_annual": r["invest_terminal_annual"],
        "invest_terminal_monthly": r["invest_terminal_monthly"],
        "invest_net_gain_annual": r["invest_net_gain_annual"],
        "breakeven_return_vs_opt1": r["breakeven_return_vs_opt1"],
        "breakeven_return_vs_opt2": r["breakeven_return_vs_opt2"],
        "winner_vs_opt1": r["winner_vs_opt1"],
        "winner_vs_opt2": r["winner_vs_opt2"],
    }


def _sell_funds(data: SellPlanInput):
    """Check a sell-plan request and turn it into engine inputs."""
    if sum(len(f.lots) for f in data.funds) > MAX_LOTS:
        raise HTTPException(422, f"Please keep it to {MAX_LOTS} purchases in total.")
    for f in data.funds:
        if any(lot.bought > data.sell_on for lot in f.lots):
            raise HTTPException(422, f"{f.name}: a purchase date is after today.")
    return [Fund(f.name, f.kind, f.nav, [Lot(l.bought, l.units, l.cost) for l in f.lots],
                 f.exit_load, f.exit_load_days, f.nav_31jan2018)
            for f in data.funds]


@app.post("/sell-plan")
def sell_plan_endpoint(data: SellPlanInput):
    """Cheapest way to raise the target from mutual funds today (FIFO, lot by lot)."""
    funds = _sell_funds(data)
    payer_on = payers_from(data.sell_on, data.slab_rate, data.surcharge, data.ltcg_exemption_used)
    return cheapest_plan(funds, data.target, data.sell_on, payer_on(data.sell_on))


@app.post("/sell-plan/timing")
def sell_plan_timing_endpoint(data: SellPlanInput):
    """Whether waiting until need_by, or splitting the sale across 31 March, costs less."""
    funds = _sell_funds(data)
    if data.need_by is None or data.need_by <= data.sell_on:
        raise HTTPException(422, "Please pick a date after today for when you need the money.")
    return timing(funds, data.target, data.sell_on, data.need_by, data.slab_rate,
                  data.surcharge, data.ltcg_exemption_used)


@app.post("/tax-regime")
def tax_regime_endpoint(data: TaxRegimeInput):
    """Old vs New income tax regime comparison (FY 2026-27 slabs)."""
    r = compare_regimes(data.gross_income, data.old_regime_deductions)
    be = breakeven_deduction(data.gross_income)
    old, new = r["old"], r["new"]
    return {
        "old": {
            "taxable_income": old.taxable_income,
            "tax_before_rebate": old.tax_before_rebate,
            "tax_after_rebate": old.tax_after_rebate,
            "surcharge": old.surcharge,
            "cess": old.cess,
            "total_tax": old.total_tax,
            "effective_rate": old.effective_rate,
        },
        "new": {
            "taxable_income": new.taxable_income,
            "tax_before_rebate": new.tax_before_rebate,
            "tax_after_rebate": new.tax_after_rebate,
            "surcharge": new.surcharge,
            "cess": new.cess,
            "total_tax": new.total_tax,
            "effective_rate": new.effective_rate,
        },
        "winner": r["winner"],
        "savings": r["savings"],
        "breakeven_old_deductions": be,
    }