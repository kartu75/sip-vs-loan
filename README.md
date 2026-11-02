# SIP vs Loan · Decision Studio

A calculator for the Indian homebuyer's dilemma: when you need cash for a house and hold SIP (mutual fund) investments, should you **redeem them, take a home loan, or split the difference**? It compares net wealth over time for each option.

## Features

- **Redeem / Loan / Hybrid**: one engine evaluates all three, including LTCG tax on redemption
- **Step-up SIP**: SIP contributions that grow each year with salary
- **Optimal split** and **break-even finder**: the equity return and loan rate where the winner flips
- **Monte Carlo**: a distribution of market paths, so results come out as probabilities
- **Rent vs buy**, **prepay loan vs invest**, and **old vs new tax regime** comparisons
- **Raise cash (sell plan)**: enter your funds and each purchase, and get the cheapest way to raise a given amount: which funds to redeem and how many units (oldest units first, as fund houses do), with STCG/LTCG, the ₹1.25 L exemption, grandfathering, exit loads, ELSS lock-ins and loss set-off. It also checks whether waiting or splitting the sale across 31 March costs less
- **Plain-English explanations** written by Gemini from the model's already-computed numbers (the LLM does no math)

## Project structure

| File | Purpose |
|---|---|
| `model.py` | Core SIP vs loan engine (all calculations) |
| `rentbuy.py`, `prepay.py`, `tax.py` | Rent vs buy, prepay vs invest, tax regime modules |
| `sellplan.py` | Sell plan: cheapest way to raise cash from mutual funds, lot by lot. `python sellplan.py` runs the hand-worked examples and checks the search against an exact solver (needs `pip install scipy`, which the app itself doesn't use) |
| `explain.py` | Gemini narration layer |
| `backend.py` | FastAPI backend exposing the engine as an API |
| `frontend/` | React front end (Vite) |
| `practiceapi.py` | FastAPI practice/scratch file |

## Setup

Requires Python 3.11+.

```bash
pip install -r requirements.txt
```

For the AI explanations, copy `.env.example` to `.env` and add your Gemini API key:

```
GEMINI_API_KEY=your-gemini-api-key-here
```

The calculators work without a key; only the explanation feature needs it.

## Running

FastAPI backend (interactive docs at http://127.0.0.1:8000/docs):

```bash
uvicorn backend:app --reload
```

## Frontend

React on Vite, in `frontend/`. Start the FastAPI backend first, then in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. It calls `http://127.0.0.1:8000` unless you set `VITE_API_URL`.

## Dependencies

fastapi, uvicorn, pydantic, google-genai, python-dotenv (pinned versions in `requirements.txt`).
