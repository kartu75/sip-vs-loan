"""
SIP vs Loan — Decision Studio
=============================
A calculator for the Indian homebuyer's dilemma: redeem your mutual funds,
take a home loan, or split the difference?

Presentation layer only. Every number comes from model.py.
Run:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
from model import (compare, evaluate_split, find_optimal_split,
                   find_breakevens, monte_carlo)
from explain import explain_decision, facts_from_results

# ----------------------------------------------------------
# PAGE + LIGHT STYLING
# ----------------------------------------------------------
st.set_page_config(page_title="SIP vs Loan · Decision Studio",
                   page_icon="🏠", layout="wide")

st.markdown("""
<style>
  .big-verdict {font-size:2rem; font-weight:700; margin:0.2rem 0;}
  .sub {color:#8b949e; font-size:0.95rem;}
  div[data-testid="stMetricValue"] {font-size:1.5rem;}
  .stTabs [data-baseweb="tab-list"] {gap:2rem;}
</style>
""", unsafe_allow_html=True)

st.title("🏠 SIP vs Loan · Decision Studio")
st.markdown('<p class="sub">You need cash for a house and you hold mutual fund '
            'investments. Sell them, borrow, or split? You control every '
            'assumption — this is a calculator, not advice.</p>',
            unsafe_allow_html=True)

# ----------------------------------------------------------
# SIDEBAR — ALL INPUTS
# ----------------------------------------------------------
with st.sidebar:
    st.header("Your numbers")

    corpus = st.number_input("SIP corpus today (₹)", 0, value=1_500_000, step=50_000)
    invested = st.number_input("Amount invested (₹)", 0, value=1_000_000, step=50_000,
                               help="What you actually put in — sets taxable gains")
    cash_need = st.number_input("Cash needed for house (₹)", 0, value=1_500_000, step=50_000)
    monthly_sip = st.number_input("Monthly SIP (₹)", 0, value=20_000, step=1_000)

    st.divider()
    loan_tenure = st.number_input("Loan tenure (years)", 1, 30, 15)
    loan_rate = st.slider("Loan interest rate (%)", 6.0, 15.0, 9.0, 0.1) / 100
    equity_return = st.slider("Expected equity return (%)", 6.0, 18.0, 12.0, 0.5) / 100
    tax_slab = st.selectbox("Income tax slab", [0.05, 0.10, 0.20, 0.30],
                            index=3, format_func=lambda x: f"{int(x*100)}%")
    regime = st.radio("Tax regime", ["old", "new"], horizontal=True,
                      format_func=str.capitalize)

    st.divider()
    st.caption("Advanced")
    stepup_pct = st.slider("Step-up SIP: grow SIP each year (%)", 0, 20, 0, 1,
                           help="Model a SIP that rises as your salary grows")
    reinvest_emi = st.toggle("Fair mode: reinvest freed-up EMI",
                             value=False,
                             help="If you borrow less, invest the EMI you save. "
                                  "Makes every path use the same monthly cash budget.")
    horizon = st.number_input("Focus year", 1, 40, 15,
                              help="All results below recalculate for this year")

# bundle
ARGS = dict(corpus=corpus, invested=invested, cash_need=cash_need,
            monthly_sip=monthly_sip, loan_tenure=loan_tenure, loan_rate=loan_rate,
            equity_return=equity_return, tax_slab=tax_slab)
EXTRA = dict(stepup_rate=stepup_pct/100, reinvest_emi=reinvest_emi)
TAX = dict(ltcg_exemption=125_000, ltcg_rate=0.125,
           sec_24b_limit=200_000, sec_80c_limit=150_000)

def inr(x):
    """Indian-style short format: ₹1.23 Cr / ₹45.6 L."""
    if abs(x) >= 1e7:
        return f"₹{x/1e7:.2f} Cr"
    if abs(x) >= 1e5:
        return f"₹{x/1e5:.1f} L"
    return f"₹{x:,.0f}"

# core numbers used across tabs
results = compare(**ARGS, **EXTRA, horizons=(horizon,))
redeem_w = results["redeem"][horizon]
loan_w   = results[f"loan_{regime}"][horizon]
winner   = "Take the loan" if loan_w > redeem_w else "Redeem the SIP"
gap      = abs(loan_w - redeem_w)

# ----------------------------------------------------------
# HEADLINE STRIP
# ----------------------------------------------------------
h1, h2, h3, h4 = st.columns(4)
h1.metric("Monthly EMI", inr(results["emi"]))
h2.metric(f"Redeem → yr {horizon}", inr(redeem_w))
h3.metric(f"Loan → yr {horizon}", inr(loan_w))
verdict_word = "Loan" if loan_w > redeem_w else "Redeem"
h4.metric("Verdict", verdict_word, delta=inr(gap))

st.divider()

# ----------------------------------------------------------
# PLAIN-ENGLISH EXPLANATION  (LLM, button-triggered)
# ----------------------------------------------------------
with st.expander("🗣️  Explain this for me (plain English)", expanded=False):
    st.caption("Uses AI to describe your results in simple language. "
               "Runs only when you click — not on every change.")
    if st.button("Generate explanation", type="primary"):
        with st.spinner("Writing your explanation…"):
            # explanation needs a Monte Carlo win-probability; run a quick one
            mc_quick = monte_carlo(
                corpus=corpus, invested=invested, cash_need=cash_need,
                monthly_sip=monthly_sip, loan_tenure=loan_tenure,
                loan_rate=loan_rate, tax_slab=tax_slab, regime=regime,
                horizon=horizon, mean_return=equity_return, volatility=0.18,
                n_sims=500, **EXTRA)
            facts = facts_from_results(results, mc_quick, horizon, regime,
                                       equity_return, loan_rate)
            st.markdown(explain_decision(facts))

st.divider()

# ----------------------------------------------------------
# TABS
# ----------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["⚖️ Compare", "🎚️ Optimal Split", "🎯 Robustness", "🎲 Monte Carlo"])

# ========== TAB 1: COMPARE ==========
with tab1:
    st.subheader(f"At year {horizon} ({regime} regime): {winner}")
    st.caption(f"The two paths differ by {inr(gap)} at year {horizon}.")

    # wealth trajectory over time (1..horizon) for both paths
    yr_range = list(range(1, horizon + 1))
    traj = compare(**ARGS, **EXTRA, horizons=tuple(yr_range))
    traj_df = pd.DataFrame({
        "Redeem": [traj["redeem"][y] for y in yr_range],
        "Loan":   [traj[f"loan_{regime}"][y] for y in yr_range],
    }, index=yr_range)
    traj_df.index.name = "Year"
    st.markdown("**Wealth trajectory**")
    st.line_chart(traj_df)

    cc1, cc2 = st.columns(2)
    with cc1:
        st.markdown("**Snapshot table**")
        snap = pd.DataFrame({
            "Path": ["Redeem", "Loan (new)", "Loan (old)"],
            f"Year {horizon}": [results["redeem"][horizon],
                                 results["loan_new"][horizon],
                                 results["loan_old"][horizon]],
        }).set_index("Path")
        st.dataframe(snap.style.format("₹{:,.0f}"))
    with cc2:
        d = results["redeem_details"]
        st.markdown("**If you redeem**")
        st.write(f"- LTCG tax paid: {inr(d['ltcg_tax'])}")
        st.write(f"- Shortfall borrowed: {inr(d['loan_amount'])}")
        if stepup_pct:
            st.write(f"- SIP steps up {stepup_pct}%/yr")
        if reinvest_emi:
            st.write("- Fair mode ON: freed-up EMI reinvested")

# ========== TAB 2: OPTIMAL SPLIT ==========
with tab2:
    st.subheader("Best redeem / borrow mix")
    best_frac, best_wealth, curve = find_optimal_split(
        **ARGS, **EXTRA, regime=regime, target_horizon=horizon)
    st.success(f"**Redeem {best_frac*100:.0f}% · Borrow {(1-best_frac)*100:.0f}%** "
               f"→ richest at year {horizon}: **{inr(best_wealth)}**")

    curve_df = pd.DataFrame({"Net wealth": [w for _, w in curve]},
                            index=[f*100 for f, _ in curve])
    curve_df.index.name = "Redeem %"
    st.markdown(f"**Wealth at year {horizon} for every split**")
    st.area_chart(curve_df)
    st.caption("0% = full loan · 100% = full redemption. The peak is optimal.")

    # optimal split across reference horizons
    st.markdown("**How the optimal split shifts with time**")
    ref_years = sorted(set([horizon, 5, 10, 15, 20, 25, 30]))
    rows = []
    for y in ref_years:
        f, w, _ = find_optimal_split(**ARGS, **EXTRA, regime=regime, target_horizon=y)
        rows.append({"Year": y, "Redeem %": f"{f*100:.0f}%",
                     "Borrow %": f"{(1-f)*100:.0f}%", "Wealth": w,
                     "": "◄ focus" if y == horizon else ""})
    st.dataframe(pd.DataFrame(rows).set_index("Year")
                 .style.format({"Wealth": "₹{:,.0f}"}))

# ========== TAB 3: ROBUSTNESS (break-even) ==========
with tab3:
    st.subheader("How safe is this verdict?")
    be = find_breakevens(**ARGS, **EXTRA, regime=regime, horizon=horizon)
    eq_be, lr_be = be["equity_breakeven"], be["loan_breakeven"]

    bc1, bc2 = st.columns(2)
    with bc1:
        if eq_be is None:
            st.metric("Equity break-even", "—")
            st.caption("Loan wins across all realistic equity returns.")
        else:
            st.metric("Equity break-even", f"{eq_be*100:.1f}%")
            st.caption(f"Loan wins while equity return > {eq_be*100:.1f}%. "
                       f"You assumed {equity_return*100:.1f}%.")
    with bc2:
        if lr_be is None:
            st.metric("Loan-rate break-even", "—")
            st.caption("Loan wins across all realistic loan rates.")
        else:
            st.metric("Loan-rate break-even", f"{lr_be*100:.1f}%")
            st.caption(f"Loan wins while loan rate < {lr_be*100:.1f}%. "
                       f"You assumed {loan_rate*100:.1f}%.")

    # robustness verdict
    robust = (eq_be is not None and equity_return > eq_be and
              lr_be is not None and loan_rate < lr_be)
    if robust:
        margin = (equity_return - eq_be) * 100
        st.info(f"🛡️ **Robust.** Your equity assumption clears its break-even by "
                f"{margin:.1f} points and your loan rate sits well under its ceiling. "
                f"The loan verdict holds across a wide range — it isn't a coin-flip.")
    elif eq_be is not None and abs(equity_return - eq_be) < 0.015:
        st.warning("⚠️ **Marginal.** You're sitting right at the equity break-even — "
                   "a small change in assumptions flips the answer. Treat the verdict "
                   "with caution.")

    # visual: where you sit vs break-even on equity
    if eq_be is not None:
        st.markdown("**Your equity assumption vs the break-even**")
        span = pd.DataFrame({
            "value": [eq_be*100, equity_return*100],
        }, index=["Break-even", "Your assumption"])
        st.bar_chart(span)

# ========== TAB 4: MONTE CARLO ==========
with tab4:
    st.subheader("What if returns aren't guaranteed?")
    st.caption("A single 12% assumption hides risk. Here we simulate thousands of "
               "possible market lives and count how often each path wins.")

    mc1, mc2, mc3 = st.columns(3)
    vol = mc1.slider("Market volatility (%)", 5, 30, 18, 1,
                     help="Higher = wilder swings. ~18% is typical for Indian equity.") / 100
    n_sims = mc2.select_slider("Simulations", [500, 1000, 2000, 5000], value=2000)
    mc3.metric("Mean return used", f"{equity_return*100:.1f}%")

    with st.spinner(f"Running {n_sims:,} simulated market lives…"):
        mc = monte_carlo(corpus=corpus, invested=invested, cash_need=cash_need,
                         monthly_sip=monthly_sip, loan_tenure=loan_tenure,
                         loan_rate=loan_rate, tax_slab=tax_slab, regime=regime,
                         horizon=horizon, mean_return=equity_return, volatility=vol,
                         n_sims=n_sims, **EXTRA)

    prob = mc["loan_win_prob"] * 100
    st.markdown(f'<p class="big-verdict">Loan wins in '
                f'{prob:.0f}% of {n_sims:,} simulated lives</p>',
                unsafe_allow_html=True)
    st.progress(prob / 100)

    if prob >= 70:
        st.success("The loan wins in a strong majority of futures — a confident call.")
    elif prob >= 55:
        st.info("The loan wins more often than not, but a meaningful minority of "
                "market paths favour redeeming. Consider your risk appetite.")
    else:
        st.warning("This is close to a coin-flip. The 'right' answer depends heavily "
                   "on how markets actually behave — redeeming is far from wrong.")

    st.markdown("**Range of outcomes** (P10 = unlucky markets, P90 = lucky)")
    dist = pd.DataFrame({
        "Loan":   [mc["loan_p10"], mc["loan_p50"], mc["loan_p90"]],
        "Redeem": [mc["redeem_p10"], mc["redeem_p50"], mc["redeem_p90"]],
    }, index=["P10 (bad)", "P50 (median)", "P90 (good)"])
    st.dataframe(dist.style.format("₹{:,.0f}"))
    st.bar_chart(dist)

    st.caption("Notice: in unlucky markets (P10), redeeming often wins — being "
               "debt-free protects you when returns disappoint. That trade-off is "
               "the real story a single-number calculator hides.")

st.divider()
st.caption("Calculations depend entirely on your assumptions — especially equity "
           "return, which is never guaranteed. This tool computes; it does not advise.")