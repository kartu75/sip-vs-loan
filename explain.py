"""
explain.py — the LLM narration layer
====================================
Turns the model's VERIFIED NUMBERS into a plain-English explanation.

Golden rule: the LLM does NO math. model.py already computed and verified
every number; we hand the LLM those exact figures and ask it only to WRITE.
Feed facts, get a story — never let it calculate.

Uses the current `google-genai` SDK (the older `google-generativeai` is
deprecated).  Install with:  pip install google-genai python-dotenv
"""

import os
from dotenv import load_dotenv
from google import genai            # the NEW sdk (google-genai)

# ---- load the secret key from .env (never hard-code it) ----
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# current fast model; change here if Google renames it again
DEFAULT_MODEL = "gemini-3.6-flash"


def _format_inr(x):
    """Readable rupee amounts for the prompt."""
    if abs(x) >= 1e7:
        return f"Rs {x/1e7:.2f} crore"
    if abs(x) >= 1e5:
        return f"Rs {x/1e5:.2f} lakh"
    return f"Rs {x:,.0f}"


def build_prompt(facts):
    """Assemble instructions + the numbers WE control into one prompt string."""
    return f"""You are a calm, plain-spoken financial explainer for an Indian
audience. A user is deciding whether to REDEEM their mutual fund SIP to buy a
house, or take a HOME LOAN and keep investing. A verified calculator has already
produced the exact numbers below.

Your job: explain what these numbers mean in simple language a non-expert
(say, a 45-year-old with no finance background) can understand.

STRICT RULES:
- Use ONLY the numbers given below. Do NOT calculate or invent any figure.
- Do NOT give a personalized buy/sell recommendation. Explain the trade-off and
  let them decide. This is a calculator, not advice.
- State the risk clearly: the loan winning depends on assumed returns that are
  not guaranteed.
- Keep it to 3 short paragraphs. Warm, clear, no jargon.

THE NUMBERS:
- Time horizon: {facts['horizon']} years
- If they REDEEM the SIP, projected wealth: {_format_inr(facts['redeem_wealth'])}
- If they take the LOAN, projected wealth: {_format_inr(facts['loan_wealth'])}
- Difference between the two: {_format_inr(facts['gap'])}
- Which path is mathematically ahead here: {facts['winner']}
- Monthly EMI if they take the loan: {_format_inr(facts['emi'])}
- Assumed equity return: {facts['equity_return_pct']:.1f}% per year
- Loan interest rate: {facts['loan_rate_pct']:.1f}% per year
- Monte Carlo result: the loan comes out ahead in {facts['loan_win_prob_pct']:.0f}%
  of thousands of simulated market scenarios
- Important nuance: in the worst 10% of market outcomes, redeeming (being
  debt-free) often ends up better.

Write the explanation now."""


def explain_decision(facts, model_name=DEFAULT_MODEL):
    """
    Main entry point. Takes a `facts` dict, returns the LLM's plain-English text.
    Wrapped so a bad key or network hiccup returns a message instead of crashing.
    """
    if not API_KEY:
        return ("⚠️ No API key found. Create a .env file in this folder with "
                "GEMINI_API_KEY=your_key")

    try:
        client = genai.Client(api_key=API_KEY)          # authenticate (new SDK)
        response = client.models.generate_content(       # THE API CALL
            model=model_name,
            contents=build_prompt(facts),
        )
        return response.text
    except Exception as e:
        return f"⚠️ Could not generate explanation right now. ({type(e).__name__}: {e})"


def facts_from_results(results, mc, horizon, regime, equity_return, loan_rate):
    """Flatten the model's output dicts into the facts dict build_prompt wants."""
    redeem_wealth = results["redeem"][horizon]
    loan_wealth   = results[f"loan_{regime}"][horizon]
    return {
        "horizon": horizon,
        "redeem_wealth": redeem_wealth,
        "loan_wealth": loan_wealth,
        "gap": abs(loan_wealth - redeem_wealth),
        "winner": "the loan" if loan_wealth > redeem_wealth else "redeeming",
        "emi": results["emi"],
        "equity_return_pct": equity_return * 100,
        "loan_rate_pct": loan_rate * 100,
        "loan_win_prob_pct": mc["loan_win_prob"] * 100,
    }


if __name__ == "__main__":
    demo = {
        "horizon": 15, "redeem_wealth": 9_779_758, "loan_wealth": 12_196_344,
        "gap": 2_416_586, "winner": "the loan", "emi": 15_214,
        "equity_return_pct": 12.0, "loan_rate_pct": 9.0, "loan_win_prob_pct": 68.0,
    }
    print("Calling Gemini with demo numbers...\n")
    print(explain_decision(demo))