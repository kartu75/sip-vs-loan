import { useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// ----------------------------------------------------------
// API
// ----------------------------------------------------------

async function postJSON(endpoint, body) {
  let res;
  try {
    res = await fetch(`${API_URL}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error(`Can't reach the backend at ${API_URL}. Is uvicorn running?`);
  }

  // A 500 from FastAPI is plain text, so don't assume the reply is JSON.
  const text = await res.text();
  let data = null;
  try {
    data = JSON.parse(text);
  } catch {
    data = null;
  }

  if (!res.ok) {
    const detail = data?.detail;
    const message = Array.isArray(detail)
      ? detail.map((d) => `${d.loc?.at(-1)}: ${d.msg}`).join("; ")
      : detail || "The backend couldn't calculate this. Please check your numbers.";
    throw new Error(message);
  }
  return data;
}

// ----------------------------------------------------------
// FORMATTING
// ----------------------------------------------------------

// Short form for metric boxes and verdict lines.
function inr(x) {
  const sign = x <= -0.5 ? "-" : "";
  const a = Math.abs(x);
  if (a >= 1e7) return `${sign}₹${(a / 1e7).toFixed(2)} Cr`;
  if (a >= 1e5) return `${sign}₹${(a / 1e5).toFixed(1)} L`;
  return `${sign}₹${Math.round(a).toLocaleString("en-IN")}`;
}

// Exact rupees for tables, so results can be checked against the Sheets.
function inrFull(x) {
  const sign = x <= -0.5 ? "-" : "";
  return `${sign}₹${Math.round(Math.abs(x)).toLocaleString("en-IN")}`;
}

const pct = (decimal, digits = 2) => `${(decimal * 100).toFixed(digits)}%`;

// ----------------------------------------------------------
// STYLES
// ----------------------------------------------------------

const SERIF = "Georgia, 'Times New Roman', serif";
const GOLD = "#d4af7a";

const S = {
  page: {
    minHeight: "100vh",
    background: "#0a0a0a",
    color: "#f5f5f0",
    fontFamily: "'Inter', system-ui, sans-serif",
    padding: "0 24px 120px",
    boxSizing: "border-box",
  },
  content: { maxWidth: 900, margin: "0 auto" },
  nav: { display: "flex", flexWrap: "wrap", gap: 8, padding: "24px 0 48px" },
  navButton: {
    background: "transparent",
    color: "#6a6a62",
    border: "1px solid #1f1f1d",
    borderRadius: 8,
    padding: "10px 16px",
    fontSize: 13,
    fontWeight: 500,
    fontFamily: "inherit",
    cursor: "pointer",
  },
  navButtonActive: { color: GOLD, border: `1px solid ${GOLD}` },
  brand: {
    textTransform: "uppercase",
    letterSpacing: "0.35em",
    fontSize: 14,
    fontWeight: 600,
    color: GOLD,
    marginBottom: 32,
  },
  hero: {
    fontFamily: SERIF,
    fontSize: "clamp(48px, 8vw, 96px)",
    lineHeight: 1.02,
    fontWeight: 500,
    letterSpacing: "-0.02em",
    margin: "0 0 24px",
  },
  subtitle: { fontSize: 18, lineHeight: 1.5, color: "#8a8a82", maxWidth: 520, margin: "0 0 64px" },
  label: {
    textTransform: "uppercase",
    letterSpacing: "0.3em",
    fontSize: 12,
    fontWeight: 600,
    color: "#6a6a62",
    marginBottom: 24,
  },
  card: {
    background: "#111110",
    border: "1px solid #1f1f1d",
    borderRadius: 16,
    padding: 32,
    marginBottom: 24,
  },
  row: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
    padding: "14px 0",
    borderBottom: "1px solid #1a1a18",
  },
  rowLabel: { flex: "1 1 200px", fontSize: 15, color: "#b8b8b0" },
  input: {
    flex: "0 1 180px",
    width: 180,
    minWidth: 0,
    marginLeft: "auto",
    boxSizing: "border-box",
    background: "#0a0a0a",
    border: "1px solid #2a2a27",
    borderRadius: 8,
    color: "#f5f5f0",
    fontFamily: "inherit",
    fontSize: 15,
    padding: "10px 12px",
    textAlign: "right",
  },
  primary: {
    background: "#f5f5f0",
    color: "#0a0a0a",
    border: "none",
    borderRadius: 10,
    padding: "16px 40px",
    fontFamily: "inherit",
    fontSize: 14,
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    cursor: "pointer",
    marginTop: 24,
  },
  ghost: {
    background: "transparent",
    color: GOLD,
    border: "1px solid #3a3a35",
    borderRadius: 10,
    padding: "12px 24px",
    fontFamily: "inherit",
    fontSize: 14,
    fontWeight: 500,
    cursor: "pointer",
  },
  disabled: { opacity: 0.6, cursor: "wait" },
  bigNumber: { fontFamily: SERIF, fontSize: 40, lineHeight: 1.1 },
  verdict: { fontFamily: SERIF, fontSize: 32, lineHeight: 1.25, color: GOLD, margin: "24px 0 0" },
  qualifier: { fontFamily: "'Inter', system-ui, sans-serif", fontSize: 16, color: "#6a6a62" },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", // stacks on mobile
    gap: 16,
  },
  metric: {
    background: "#0a0a0a",
    border: "1px solid #1f1f1d",
    borderRadius: 12,
    padding: 20,
    textAlign: "center",
  },
  metricLabel: {
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    fontSize: 11,
    color: "#8a8a82",
    marginBottom: 12,
  },
  metricSub: { fontSize: 13, color: "#8a8a82", marginTop: 10 },
  note: { fontSize: 15, lineHeight: 1.6, color: "#b8b8b0", margin: "16px 0 0" },
  tableWrap: { overflowX: "auto", marginTop: 24 },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 15 },
  th: {
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    fontSize: 12,
    fontWeight: 600,
    color: "#6a6a62",
    textAlign: "right",
    padding: "10px 12px",
    borderBottom: "1px solid #1a1a18",
    whiteSpace: "nowrap",
  },
  td: {
    textAlign: "right",
    padding: "12px",
    borderBottom: "1px solid #1a1a18",
    whiteSpace: "nowrap",
  },
  tdFirst: { textAlign: "left", paddingLeft: 0, color: "#b8b8b0", whiteSpace: "normal", minWidth: 140 },
  explanation: { whiteSpace: "pre-wrap", lineHeight: 1.7, fontSize: 15, color: "#d8d8d0", margin: "24px 0 0" },
  disclaimer: { fontSize: 13, lineHeight: 1.6, color: "#6a6a62", margin: "32px 0 0" },
  error: { color: "#e06060", fontSize: 15, lineHeight: 1.6, margin: "16px 0 0" },
};

// ----------------------------------------------------------
// SHARED PIECES
// ----------------------------------------------------------

function Hero({ lines, sub }) {
  return (
    <>
      <h1 style={S.hero}>
        {lines[0]}
        <br />
        {lines[1]}
      </h1>
      <p style={S.subtitle}>{sub}</p>
    </>
  );
}

function Label({ children }) {
  return <div style={S.label}>{children}</div>;
}

function Metric({ label, value, sub }) {
  return (
    <div style={S.metric}>
      <div style={S.metricLabel}>{label}</div>
      <div style={S.bigNumber}>{value}</div>
      {sub && <div style={S.metricSub}>{sub}</div>}
    </div>
  );
}

function Verdict({ line, qualifier }) {
  return (
    <p style={S.verdict}>
      {line} <span style={S.qualifier}>{qualifier}</span>
    </p>
  );
}

function Table({ headers, rows }) {
  return (
    <div style={S.tableWrap}>
      <table style={S.table}>
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={h} style={i === 0 ? { ...S.th, textAlign: "left", paddingLeft: 0 } : S.th}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row[0]}>
              {row.map((cell, i) => (
                <td key={i} style={i === 0 ? { ...S.td, ...S.tdFirst } : S.td}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Button({ variant = "primary", busy, busyText, onClick, children }) {
  const style = variant === "primary" ? S.primary : S.ghost;
  return (
    <button style={busy ? { ...style, ...S.disabled } : style} disabled={busy} onClick={onClick}>
      {busy ? busyText : children}
    </button>
  );
}

// ----------------------------------------------------------
// FORMS
// A field is { key, label, value, kind, signed }.
//   kind "pct": typed as 12, sent as 0.12 (the ONE place rates convert)
//   kind "int": whole number of 1 or more (tenures, horizons)
//   signed:     may go below zero (returns and growth rates)
// ----------------------------------------------------------

function buildBody(fields, values) {
  const body = {};
  for (const f of fields) {
    const raw = String(values[f.key]).replace(/,/g, "").trim();
    const n = Number(raw);
    if (raw === "" || !Number.isFinite(n)) throw new Error(`${f.label}: please enter a number.`);
    if (f.kind === "int" && (!Number.isInteger(n) || n < 1)) {
      throw new Error(`${f.label}: please enter a whole number of 1 or more.`);
    }
    if (n < 0 && !f.signed) throw new Error(`${f.label}: can't be negative.`);
    if (f.kind === "pct" && Math.abs(n) > 100) throw new Error(`${f.label}: please enter a percentage up to 100.`);
    body[f.key] = f.kind === "pct" ? n / 100 : n;
  }
  return body;
}

function useCalculator(fields, run) {
  const [values, setValues] = useState(() =>
    Object.fromEntries(fields.map((f) => [f.key, f.value]))
  );
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const setField = (key, value) => setValues((v) => ({ ...v, [key]: value }));

  const submit = async () => {
    setError("");
    setResult(null);
    setLoading(true);
    try {
      setResult(await run(buildBody(fields, values)));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return { values, setField, result, error, loading, submit };
}

function Fields({ fields, form }) {
  return fields.map((f) => (
    <label key={f.key} style={S.row}>
      <span style={S.rowLabel}>{f.label}</span>
      <input
        style={S.input}
        inputMode="decimal"
        value={form.values[f.key]}
        onChange={(e) => form.setField(f.key, e.target.value)}
      />
    </label>
  ));
}

function NumbersCard({ fields, form, extra }) {
  return (
    <div style={S.card}>
      <Label>Your numbers</Label>
      <Fields fields={fields} form={form} />
      {extra}
      <Button busy={form.loading} busyText="Calculating…" onClick={form.submit}>
        Calculate
      </Button>
      {form.error && <p style={S.error}>{form.error}</p>}
    </div>
  );
}

// ----------------------------------------------------------
// MODULE 1: REDEEM VS LOAN
// ----------------------------------------------------------

const SIP_FIELDS = [
  { key: "corpus", label: "Current SIP value (₹)", value: "1500000" },
  { key: "invested", label: "Amount you invested (₹)", value: "1000000" },
  { key: "cash_need", label: "Cash needed for the home (₹)", value: "1500000" },
  { key: "monthly_sip", label: "Monthly SIP (₹)", value: "20000" },
  { key: "loan_tenure", label: "Loan tenure (years)", value: "15", kind: "int" },
  { key: "loan_rate", label: "Loan rate (% a year)", value: "9", kind: "pct" },
  { key: "equity_return", label: "Equity return (% a year)", value: "12", kind: "pct", signed: true },
  { key: "tax_slab", label: "Tax slab (%)", value: "30", kind: "pct" },
  { key: "horizon", label: "Horizon (years)", value: "15", kind: "int" },
  { key: "stepup_rate", label: "SIP step-up (% a year)", value: "0", kind: "pct" },
];

function SipVsLoan() {
  const [regime, setRegime] = useState("old");
  const [reinvestEmi, setReinvestEmi] = useState(false);
  // Each holds { for: body, loading, data, error }. "for" ties a reply to the
  // Calculate run that asked for it, so a late reply can't land on newer numbers.
  const [mc, setMc] = useState(null);
  const [explain, setExplain] = useState(null);

  const form = useCalculator(SIP_FIELDS, async (fields) => {
    const body = { ...fields, regime, reinvest_emi: reinvestEmi };
    setMc(null);
    setExplain(null);
    const [calc, split, breakeven] = await Promise.all([
      postJSON("/calculate", body),
      postJSON("/optimal-split", body),
      postJSON("/breakeven", body),
    ]);
    return { body, calc, split, breakeven };
  });
  const r = form.result;

  const runExtra = async (setState, endpoint, extraBody) => {
    const body = r.body;
    const settle = (patch) =>
      setState((cur) => (cur?.for === body ? { for: body, ...patch } : cur));
    setState({ for: body, loading: true });
    try {
      settle({ data: await postJSON(endpoint, { ...body, ...extraBody }) });
    } catch (e) {
      settle({ error: e.message });
    }
  };

  const flips = () => {
    const { equity_breakeven_pct: eq, loan_breakeven_pct: loan } = r.breakeven;
    if (eq === null && loan === null) return "Winner doesn't flip: no flip in range.";
    const part = (name, value) =>
      value === null ? `${name}: no flip in range` : `${name} crosses ${value}%`;
    return `Winner flips if ${part("equity return", eq)} / ${part("loan rate", loan)}.`;
  };

  // explain.py reports failures as normal text starting with a warning sign.
  const explanation = explain?.data?.explanation ?? "";
  const explainFailed = explanation.startsWith("⚠️");

  return (
    <>
      <Hero
        lines={["crafted for the", "indecisive investor"]}
        sub="Redeem your investments or take a loan to fund a home? Enter your numbers. Every assumption is yours. This is a calculator, not advice."
      />
      <NumbersCard
        fields={SIP_FIELDS}
        form={form}
        extra={
          <>
            <label style={S.row}>
              <span style={S.rowLabel}>Tax regime</span>
              <select style={S.input} value={regime} onChange={(e) => setRegime(e.target.value)}>
                <option value="old">Old</option>
                <option value="new">New</option>
              </select>
            </label>
            <label style={S.row}>
              <span style={S.rowLabel}>Reinvest the EMI when comparing</span>
              <button
                type="button"
                aria-pressed={reinvestEmi}
                style={{ ...S.ghost, ...S.input, flex: "0 1 180px", textAlign: "center" }}
                onClick={() => setReinvestEmi((on) => !on)}
              >
                {reinvestEmi ? "On" : "Off"}
              </button>
            </label>
          </>
        }
      />

      {r && (
        <>
          <div style={S.card}>
            <Label>The verdict</Label>
            <div style={S.grid}>
              <Metric label="Monthly EMI" value={inr(r.calc.emi)} />
              <Metric label="If you redeem" value={inr(r.calc.redeem_wealth)} />
              <Metric label="If you take the loan" value={inr(r.calc.loan_wealth)} />
            </div>
            <Verdict
              line={r.calc.winner === "loan" ? "Take the loan" : "Redeem the SIP"}
              qualifier={`by ${inr(r.calc.gap)} at year ${r.body.horizon}`}
            />
            <p style={S.note}>
              LTCG tax if you redeem: {inrFull(r.calc.redeem_details.ltcg_tax)}. Shortfall borrowed
              to cover it: {inrFull(r.calc.redeem_details.shortfall_borrowed)}.
            </p>
          </div>

          <div style={S.card}>
            <Label>Optimal split</Label>
            <div style={{ ...S.verdict, marginTop: 0 }}>
              Redeem {r.split.best_redeem_pct}% · Borrow {r.split.best_borrow_pct}%
            </div>
            <p style={S.note}>
              Richest outcome at year {r.body.horizon}: {inr(r.split.best_wealth)}
            </p>
            <p style={S.note}>{flips()}</p>
          </div>

          <div style={S.card}>
            <Label>Risk analysis</Label>
            <Button
              variant="ghost"
              busy={mc?.loading}
              busyText="Running…"
              onClick={() => runExtra(setMc, "/montecarlo", { volatility: 0.18, n_sims: 2000 })}
            >
              Run Monte Carlo
            </Button>
            {mc?.error && <p style={S.error}>{mc.error}</p>}
            {mc?.data && (
              <>
                <Verdict
                  line={`Loan wins ${mc.data.loan_win_prob_pct}%`}
                  qualifier={`of ${mc.data.n_sims.toLocaleString("en-IN")} simulated markets`}
                />
                <Table
                  headers={["Market", "Loan", "Redeem"]}
                  rows={[
                    ["P10 (unlucky)", inr(mc.data.loan.p10), inr(mc.data.redeem.p10)],
                    ["P50 (median)", inr(mc.data.loan.p50), inr(mc.data.redeem.p50)],
                    ["P90 (lucky)", inr(mc.data.loan.p90), inr(mc.data.redeem.p90)],
                  ]}
                />
                <p style={S.note}>
                  In unlucky markets, redeeming often wins — being debt-free protects you when
                  returns disappoint.
                </p>
              </>
            )}
          </div>

          <div style={S.card}>
            <Label>In plain English</Label>
            <Button
              variant="ghost"
              busy={explain?.loading}
              busyText="Writing…"
              onClick={() => runExtra(setExplain, "/explain", { volatility: 0.18, n_sims: 500 })}
            >
              Explain this for me
            </Button>
            {explain?.error && <p style={S.error}>{explain.error}</p>}
            {explain?.data &&
              (explainFailed ? (
                <p style={S.error}>{explanation}</p>
              ) : (
                <p style={S.explanation}>{explanation}</p>
              ))}
          </div>
        </>
      )}

      <p style={S.disclaimer}>
        A calculator, not advice. Results use the constant returns you enter, and the projections
        are not guaranteed. LTCG is taxed at 12.5% above the ₹1.25 L exemption.
      </p>
    </>
  );
}

// ----------------------------------------------------------
// MODULE 2: RENT VS BUY
// ----------------------------------------------------------

const RENT_FIELDS = [
  { key: "property_price", label: "Property price (₹)", value: "10000000" },
  { key: "down_payment_pct", label: "Down payment (%)", value: "20", kind: "pct" },
  { key: "loan_rate", label: "Loan rate (% a year)", value: "9", kind: "pct" },
  { key: "loan_tenure", label: "Loan tenure (years)", value: "20", kind: "int" },
  { key: "monthly_rent", label: "Monthly rent today (₹)", value: "30000" },
  { key: "rent_growth", label: "Rent growth (% a year)", value: "5", kind: "pct", signed: true },
  { key: "property_appreciation", label: "Property appreciation (% a year)", value: "7", kind: "pct", signed: true },
  { key: "equity_return", label: "Equity return (% a year)", value: "12", kind: "pct", signed: true },
  { key: "horizon", label: "Horizon (years)", value: "15", kind: "int" },
];

function RentVsBuy() {
  const form = useCalculator(RENT_FIELDS, async (body) => ({
    ...(await postJSON("/rent-vs-buy", body)),
    horizon: body.horizon,
  }));
  const r = form.result;

  return (
    <>
      <Hero
        lines={["rent, or own the", "roof"]}
        sub="Rent and invest the difference, or buy with a loan? See who ends up wealthier. This is a calculator, not advice."
      />
      <NumbersCard fields={RENT_FIELDS} form={form} />

      {r && (
        <div style={S.card}>
          <Label>The verdict</Label>
          <div style={S.grid}>
            <Metric label="Rent + invest" value={inr(r.rent_wealth)} />
            <Metric label="Buy (sell)" value={inr(r.buy_wealth_sell)} />
            <Metric label="Buy (hold)" value={inr(r.buy_wealth_hold)} />
          </div>
          <Verdict
            line={r.winner === "buy" ? "Buy the home" : "Keep renting"}
            qualifier={`by ${inr(Math.abs(r.rent_wealth - r.buy_wealth_hold))} at year ${r.horizon}, against holding the home`}
          />
          <Table
            headers={["Detail", "Amount"]}
            rows={[
              ["EMI", inrFull(r.emi)],
              ["Down payment", inrFull(r.down_payment)],
              ["Loan amount", inrFull(r.loan_amount)],
              [`House value at year ${r.horizon}`, inrFull(r.house_value)],
              [`Outstanding loan at year ${r.horizon}`, inrFull(r.outstanding_loan)],
              [`Monthly rent at year ${r.horizon}`, inrFull(r.monthly_rent_at_year)],
              [`Monthly EMI at year ${r.horizon}`, inrFull(r.monthly_emi)],
            ]}
          />
        </div>
      )}

      <p style={S.disclaimer}>
        Excludes maintenance, property tax, stamp duty and registration. Selling assumes about 1%
        brokerage. The rent path invests the down payment plus any month's EMI-over-rent surplus.
      </p>
    </>
  );
}

// ----------------------------------------------------------
// MODULE 3: PREPAY VS INVEST
// ----------------------------------------------------------

const PREPAY_FIELDS = [
  { key: "principal", label: "Outstanding loan (₹)", value: "5000000" },
  { key: "annual_rate", label: "Loan rate (% a year)", value: "9", kind: "pct" },
  { key: "tenure_months", label: "Remaining tenure (months)", value: "180", kind: "int" },
  { key: "surplus", label: "One-time surplus (₹)", value: "500000" },
  { key: "tax_slab", label: "Tax slab (%)", value: "30", kind: "pct" },
  { key: "sec24b_cap", label: "Section 24(b) cap a year (₹)", value: "200000" },
  { key: "equity_return", label: "Equity return (% a year)", value: "12", kind: "pct", signed: true },
];

function prepayVerdict(r) {
  const beatsEmi = r.winner_vs_opt1 === "invest";
  const beatsTenure = r.winner_vs_opt2 === "invest";
  if (beatsEmi && beatsTenure) return ["Invest the surplus", "it beats both prepay options"];
  if (!beatsEmi && !beatsTenure) return ["Prepay the loan", "both options beat investing"];
  return beatsEmi
    ? ["Prepay with Reduced Tenure", "it beats investing, but investing beats Reduced EMI"]
    : ["Prepay with Reduced EMI", "it beats investing, but investing beats Reduced Tenure"];
}

function PrepayVsInvest() {
  const form = useCalculator(PREPAY_FIELDS, async (body) => {
    if (body.surplus > body.principal) {
      throw new Error("One-time surplus can't be more than the outstanding loan.");
    }
    return postJSON("/prepay-vs-invest", body);
  });
  const r = form.result;

  const breakeven = (value, name) =>
    value === null
      ? `No breakeven return in range against ${name}.`
      : `Investing beats ${name} above a ${pct(value)} return.`;

  let verdict, b, o1, o2;
  if (r) {
    verdict = prepayVerdict(r);
    b = r.baseline;
    o1 = r.option1_reduced_emi;
    o2 = r.option2_reduced_tenure;
  }

  return (
    <>
      <Hero
        lines={["prepay, or", "let it grow"]}
        sub="Got a lump sum? Put it into the home loan, or invest it instead. This is a calculator, not advice."
      />
      <NumbersCard fields={PREPAY_FIELDS} form={form} />

      {r && (
        <>
          <div style={S.card}>
            <Label>The verdict</Label>
            <div style={S.grid}>
              <Metric
                label="Reduced EMI"
                value={inr(o1.effective_benefit)}
                sub={`net benefit ${inrFull(o1.effective_benefit)}`}
              />
              <Metric
                label="Reduced Tenure"
                value={inr(o2.effective_benefit)}
                sub={`net benefit ${inrFull(o2.effective_benefit)}, ${o2.tenure_months} months`}
              />
              <Metric
                label="Invest"
                value={inr(r.invest_terminal_annual)}
                sub={`grows to ${inrFull(r.invest_terminal_annual)}, net gain ${inrFull(r.invest_net_gain_annual)}`}
              />
            </div>
            <Verdict line={verdict[0]} qualifier={verdict[1]} />
            <p style={S.note}>
              Against Reduced EMI: {r.winner_vs_opt1 === "invest" ? "invest wins" : "prepay wins"}.
              Against Reduced Tenure: {r.winner_vs_opt2 === "invest" ? "invest wins" : "prepay wins"}.
            </p>
            <p style={S.note}>
              {breakeven(r.breakeven_return_vs_opt1, "Reduced EMI")}{" "}
              {breakeven(r.breakeven_return_vs_opt2, "Reduced Tenure")}
            </p>
          </div>

          <div style={S.card}>
            <Label>The details</Label>
            <Table
              headers={["", "Baseline", "Reduced EMI", "Reduced Tenure"]}
              rows={[
                ["Monthly payment", inrFull(b.emi), inrFull(o1.monthly_payment), inrFull(o2.monthly_payment)],
                ["Tenure", `${b.tenure_months} months`, `${o1.tenure_months} months`, `${o2.tenure_months} months`],
                ["Total interest", inrFull(b.total_interest), inrFull(o1.total_interest), inrFull(o2.total_interest)],
                ["Interest saved", "—", inrFull(o1.interest_saved), inrFull(o2.interest_saved)],
                ["24(b) deduction lost", "—", inrFull(o1.tax_deduction_lost), inrFull(o2.tax_deduction_lost)],
                ["Effective benefit", "—", inrFull(o1.effective_benefit), inrFull(o2.effective_benefit)],
              ]}
            />
            <Table
              headers={["If you invest", "Amount"]}
              rows={[
                ["Terminal value (annual compounding)", inrFull(r.invest_terminal_annual)],
                ["Terminal value (monthly compounding)", inrFull(r.invest_terminal_monthly)],
                ["Net gain (annual compounding)", inrFull(r.invest_net_gain_annual)],
              ]}
            />
          </div>
        </>
      )}

      <p style={S.disclaimer}>
        Reduced EMI keeps the tenure but lowers the EMI. Reduced Tenure keeps the EMI and closes the
        loan early, saving more interest but losing more 24(b) deduction. The invest path assumes a
        constant return with no volatility modelled, and no tax on the gains.
      </p>
    </>
  );
}

// ----------------------------------------------------------
// MODULE 4: OLD VS NEW TAX
// ----------------------------------------------------------

const TAX_FIELDS = [
  { key: "gross_income", label: "Gross annual income (₹)", value: "1200000" },
  { key: "old_regime_deductions", label: "Old regime deductions (₹)", value: "250000" },
];

function taxBreakevenNote(amount) {
  if (amount === null) return "Old regime doesn't beat the new one at any deduction level here.";
  if (amount === 0) return "Old regime needs no deductions to match the new one here.";
  return `Old regime wins only if your deductions exceed ${inrFull(amount)}.`;
}

function TaxRegime() {
  const form = useCalculator(TAX_FIELDS, (body) => postJSON("/tax-regime", body));
  const r = form.result;

  return (
    <>
      <Hero
        lines={["two regimes,", "one tax bill"]}
        sub="Old or new? Enter your income and deductions to see which one costs you less. This is a calculator, not advice."
      />
      <NumbersCard fields={TAX_FIELDS} form={form} />

      {r && (
        <div style={S.card}>
          <Label>The verdict</Label>
          <div style={S.grid}>
            <Metric label="Old regime tax" value={inr(r.old.total_tax)} />
            <Metric label="New regime tax" value={inr(r.new.total_tax)} />
          </div>
          {r.winner === "tie" ? (
            <Verdict line="It's a tie" qualifier="same tax under both regimes" />
          ) : (
            <Verdict
              line={r.winner === "new" ? "New regime wins" : "Old regime wins"}
              qualifier={`saves ${inrFull(r.savings)} a year`}
            />
          )}
          <p style={S.note}>{taxBreakevenNote(r.breakeven_old_deductions)}</p>
          <Table
            headers={["", "Old regime", "New regime"]}
            rows={[
              ["Taxable income", inrFull(r.old.taxable_income), inrFull(r.new.taxable_income)],
              ["Tax before rebate", inrFull(r.old.tax_before_rebate), inrFull(r.new.tax_before_rebate)],
              ["Tax after rebate", inrFull(r.old.tax_after_rebate), inrFull(r.new.tax_after_rebate)],
              ["Cess", inrFull(r.old.cess), inrFull(r.new.cess)],
              ["Total tax", inrFull(r.old.total_tax), inrFull(r.new.total_tax)],
              ["Effective rate", pct(r.old.effective_rate), pct(r.new.effective_rate)],
            ]}
          />
        </div>
      )}

      <p style={S.disclaimer}>
        FY 2024-25 slabs. Old regime gets the ₹50,000 standard deduction plus what you enter (80C,
        80D, HRA, 24(b), NPS 80CCD(1B)). New regime gets a flat ₹75,000 standard deduction only. 87A
        rebate and marginal relief are applied automatically.
      </p>
    </>
  );
}

// ----------------------------------------------------------
// APP
// ----------------------------------------------------------

const MODULES = [
  { id: "sip", name: "Redeem vs Loan", Component: SipVsLoan },
  { id: "rent", name: "Rent vs Buy", Component: RentVsBuy },
  { id: "prepay", name: "Prepay vs Invest", Component: PrepayVsInvest },
  { id: "tax", name: "Old vs New Tax", Component: TaxRegime },
];

export default function App() {
  const [module, setModule] = useState("sip");

  return (
    <div style={S.page}>
      <div style={S.content}>
        <nav style={S.nav}>
          {MODULES.map((m) => (
            <button
              key={m.id}
              aria-current={module === m.id ? "page" : undefined}
              style={module === m.id ? { ...S.navButton, ...S.navButtonActive } : S.navButton}
              onClick={() => setModule(m.id)}
            >
              {m.name}
            </button>
          ))}
        </nav>
        <div style={S.brand}>MANKART</div>
        {/* Hidden, not unmounted, so numbers survive switching between tabs. */}
        {MODULES.map(({ id, Component }) => (
          <div key={id} style={{ display: module === id ? "block" : "none" }}>
            <Component />
          </div>
        ))}
      </div>
    </div>
  );
}
