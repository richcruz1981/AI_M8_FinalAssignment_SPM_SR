import React, { useEffect, useMemo, useState } from "react";
import { UI, SERIES, STATUS, STATUS_ORDER, SEVERITY, CMP, KPI_HEALTH } from "./theme.js";
import {
  applyFilters, countBy, healthByGroup, healthDistribution, kpiSummary, byGroupFinance, controlTotals,
  milestoneStatus, dqByRule, fmtInt, fmtMoney, fmtPct, fmtNum,
} from "./data.js";
import { DistChart, StackedChart, CompareChart, CpiChart, ProgressScatter, DONUT5 } from "./components/Charts.jsx";

const EMPTY = { portfolio: "All", program: "All", region: "All", category: "All", pm: "All", health: "All",
                search: "", activeOnly: true };
const MODES = [["bars", "Bars"], ["columns", "Columns"], ["donut", "Donut"]];
const HEALTH_KEYS = ["Green", "Amber", "Red", "No data", "Not analyzed"];
const HEALTH_COLORS = { ...STATUS, "Not analyzed": "#D5DAE3" };

function useData() {
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    fetch(`./data/kpis.json?ts=${Date.now()}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => setState({ data: d }))
      .catch((e) => setState({ error: e.message }));
  }, []);
  return state;
}

const Chip = ({ s }) => (
  <span className="chip" style={{ background: `${HEALTH_COLORS[s] || "#ccc"}22`, color: UI.ink, borderColor: HEALTH_COLORS[s] }}>
    <i style={{ background: HEALTH_COLORS[s] }} />{s}
  </span>
);

function Select({ label, value, options, onChange }) {
  return (
    <label className="fld">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="All">All</option>
        {options.map((o) => <option key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</option>)}
      </select>
    </label>
  );
}

function Card({ title, sub, children, wide, kpi }) {
  return (
    <section className={`card${wide ? " wide" : ""}`}>
      <header>
        <div>
          <h3>{kpi && <span className="kpi-tag">{kpi}</span>}{title}</h3>
          {sub && <p>{sub}</p>}
        </div>
      </header>
      {children}
    </section>
  );
}

function Tile({ label, value, sub, tone }) {
  return (
    <div className={`tile ${tone || ""}`}>
      <span>{label}</span>
      <b>{value}</b>
      {sub && <small>{sub}</small>}
    </div>
  );
}

function Drawer({ p, onClose }) {
  if (!p) return null;
  const row = (k, v) => <div className="kv"><span>{k}</span><b>{v}</b></div>;
  return (
    <div className="drawer-bg" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()}>
        <button className="x" onClick={onClose} aria-label="Close">×</button>
        <h2>{p.id}</h2>
        <p className="muted">{p.name}</p>
        <div className="meta">{p.category} · {p.region} · PM {p.pm}<br />{p.program} · {p.portfolio}</div>
        {!p.analyzed ? (
          <div className="note">No KPIs: project is {p.active ? "excluded by data-quality rules" : "closed or cancelled"}.</div>
        ) : (
          <>
            <h4>Health · KPIs 1–5 <small>calculated vs declared by PM</small></h4>
            <table className="mini">
              <tbody>
                {KPI_HEALTH.map(([k, l]) => (
                  <tr key={k}><td>{l}</td><td><Chip s={p.health[k].calc} /></td><td><Chip s={p.health[k].declared} /></td>
                    <td className={p.health[k].cmp === "Optimistic" ? "warn" : "muted"}>{p.health[k].cmp}</td></tr>
                ))}
              </tbody>
            </table>
            <h4>Performance · KPIs 6–13</h4>
            <div className="bar-cmp">
              {[["Actual % complete", p.pctComplete, SERIES[0]], ["Expected (linear)", p.pctExpected, "#9DB3E6"],
                ["Budget used", p.budgetUsedPct, SERIES[1]],
                ["Effort used", p.plannedEffort ? (100 * p.actualEffort) / p.plannedEffort : null, SERIES[2]]].map(([l, v, c]) => (
                <div key={l} className="bc"><span>{l}</span>
                  <div className="track"><div style={{ width: `${Math.min(100, v || 0)}%`, background: c }} /></div>
                  <b>{fmtPct(v, 1)}</b></div>
              ))}
            </div>
            {row("6 · % complete / gap", `${fmtPct(p.pctComplete, 1)} · ${p.gapPp} pp`)}
            {row("7–8 · Planned start → end", `${p.plannedStart} → ${p.plannedEnd}`)}
            {row("9–10 · Actual start → end", `${p.actualStart || "—"} → ${p.actualEnd || "—"}`)}
            {row("End variance", p.endVarianceDays == null ? "—" : `${p.endVarianceDays} days`)}
            {row("11–12 · Planned / actual cost", `${fmtMoney(p.plannedCost)} / ${fmtMoney(p.actualCost)}`)}
            {row("CPI · budget used", `${fmtNum(p.cpi)} · ${fmtPct(p.budgetUsedPct, 1)}`)}
            {row("13 · Planned / actual effort", `${fmtInt(p.plannedEffort)} h / ${fmtInt(p.actualEffort)} h`)}
            {p.allocatedHours != null && row("Allocated vs actual hours", `${fmtInt(p.allocatedHours)} h / ${fmtInt(p.allocActualHours)} h`)}
            <h4>Control · KPIs 14–19</h4>
            {row("14 · Milestones done / total (overdue)", `${p.milestonesDone ?? "—"} / ${p.milestonesTotal ?? "—"} (${p.milestonesOverdue ?? "—"})`)}
            {row("15 · Open risks (high)", `${p.risksOpen ?? "—"} (${p.risksHigh ?? "—"})`)}
            {row("16 · Open issues", p.issuesOpen ?? "—")}
            {row("17 · Pending decisions", p.decisionsPending ?? "—")}
            {row("18 · Pending actions (overdue)", `${p.actionsPending ?? "—"} (${p.actionsOverdue ?? "—"})`)}
            {row("19 · Pending change requests", p.changesPending ?? "—")}
            {row("Status report as of", p.srMissing ? "Missing" : `${p.srAsOf}${p.srStale ? " (stale)" : ""}`)}
            {p.alerts?.length > 0 && (<><h4>Alerts</h4><ul className="alerts">{p.alerts.map((a) => <li key={a}>{a}</li>)}</ul></>)}
          </>
        )}
        <h4>Data quality</h4>
        {p.dq.length ? <ul className="alerts">{p.dq.map((r) => <li key={r}>{r}</li>)}</ul> : <p className="muted">No findings ✓</p>}
      </aside>
    </div>
  );
}

function ProjectTable({ rows, onPick }) {
  const [sort, setSort] = useState({ k: "id", dir: 1 });
  const [page, setPage] = useState(0);
  const val = (p, k) => (k.startsWith("h.") ? (p.analyzed ? STATUS_ORDER.indexOf(p.health[k.slice(2)].calc) : 9) : p[k]);
  const sorted = useMemo(() => [...rows].sort((a, b) => {
    const x = val(a, sort.k), y = val(b, sort.k);
    return (x == null) - (y == null) || (x > y ? 1 : x < y ? -1 : 0) * sort.dir;
  }), [rows, sort]);
  useEffect(() => setPage(0), [rows]);
  const per = 15, pages = Math.max(1, Math.ceil(sorted.length / per));
  const cols = [["id", "Project"], ["name", "Name"], ["portfolio", "Portfolio"], ["program", "Program"], ["region", "Region"],
    ["category", "Category"], ["h.overall", "Overall"], ["h.schedule", "Sched."], ["h.cost", "Cost"], ["h.resources", "Res."],
    ["h.scope", "Scope"], ["pctComplete", "% compl."], ["cpi", "CPI"]];
  return (
    <>
      <div className="table-wrap">
        <table className="grid">
          <thead><tr>{cols.map(([k, l]) => (
            <th key={k} onClick={() => setSort((s) => ({ k, dir: s.k === k ? -s.dir : 1 }))}>
              {l}{sort.k === k ? (sort.dir > 0 ? " ▲" : " ▼") : ""}</th>))}</tr></thead>
          <tbody>
            {sorted.slice(page * per, page * per + per).map((p) => (
              <tr key={p.id} onClick={() => onPick(p.id)}>
                <td className="mono">{p.id}</td><td className="name">{p.name}</td><td>{p.portfolio}</td><td>{p.program}</td>
                <td>{p.region}</td><td>{p.category}</td>
                {["overall", "schedule", "cost", "resources", "scope"].map((k) => (
                  <td key={k}>{p.analyzed ? <Chip s={p.health[k].calc} /> : <span className="muted">—</span>}</td>))}
                <td className="num">{fmtPct(p.pctComplete, 0)}</td><td className="num">{fmtNum(p.cpi)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pager">
        <span>{sorted.length} projects · page {page + 1} of {pages}</span>
        <button disabled={!page} onClick={() => setPage(page - 1)}>‹ Prev</button>
        <button disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>Next ›</button>
      </div>
    </>
  );
}

export default function App() {
  const { data, error, loading } = useData();
  const [f, setF] = useState(EMPTY);
  const [mode, setMode] = useState(() => { try { return localStorage.getItem("chartMode") || "bars"; } catch { return "bars"; } });
  const [pick, setPick] = useState(null);
  useEffect(() => { try { localStorage.setItem("chartMode", mode); } catch { /* storage unavailable */ } }, [mode]);

  const projects = data?.projects || [];
  const opts = useMemo(() => {
    const uniq = (k, rows = projects) => [...new Set(rows.map((p) => p[k]))].sort();
    const inPf = f.portfolio === "All" ? projects : projects.filter((p) => p.portfolio === f.portfolio);
    return { portfolio: uniq("portfolio"), program: uniq("program", inPf), region: uniq("region"),
             category: uniq("category"), pm: uniq("pm") };
  }, [projects, f.portfolio]);
  const rows = useMemo(() => applyFilters(projects, f), [projects, f]);
  const k = useMemo(() => kpiSummary(rows), [rows]);
  const set = (key) => (v) => setF((s) => ({ ...s, [key]: v, ...(key === "portfolio" ? { program: "All" } : {}) }));
  const toggle = (key) => (v) => setF((s) => ({ ...s, [key]: s[key] === v ? "All" : v }));
  const active = Object.entries(f).filter(([key, v]) => key !== "activeOnly" && key !== "search" && v !== "All");

  if (loading) return <div className="center">Loading KPIs…</div>;
  if (error) return <div className="center">Could not load data ({error}).</div>;
  const picked = projects.find((p) => p.id === pick);
  const healthColor = (n) => HEALTH_COLORS[n] || SERIES[0];

  return (
    <div className="app">
      <header className="top">
        <div className="brand">
          <div className="logo"><span /><span /><span /></div>
          <div>
            <h1>Portfolio Health Dashboard</h1>
            <p>Status report KPIs for projects, programs and portfolios · ServiceNow SPM</p>
          </div>
        </div>
        <div className="stamp">
          <span className="badge">Synthetic demo data</span>
          <span className="lastq">Last DB query <b>{lastDbQuery(data)}</b> (CDMX)</span>
          <span>Data as of <b>{data.asOf}</b> · refreshed hourly{data.security ? ` · security check: ${data.security.blocked_fields} blocked field(s)` : ""}</span>
        </div>
      </header>

      <div className="filters">
        <Select label="Portfolio" value={f.portfolio} options={opts.portfolio} onChange={set("portfolio")} />
        <Select label="Program" value={f.program} options={opts.program} onChange={set("program")} />
        <Select label="Region" value={f.region} options={opts.region} onChange={set("region")} />
        <Select label="Category" value={f.category} options={opts.category} onChange={set("category")} />
        <Select label="Overall health" value={f.health} options={[...STATUS_ORDER, "Not analyzed"]} onChange={set("health")} />
        <Select label="Project manager" value={f.pm} options={opts.pm} onChange={set("pm")} />
        <label className="fld grow"><span>Search</span>
          <input placeholder="Project ID or name…" value={f.search} onChange={(e) => set("search")(e.target.value)} /></label>
        <div className="fld"><span>Scope</span>
          <div className="seg">
            <button className={f.activeOnly ? "on" : ""} onClick={() => setF((s) => ({ ...s, activeOnly: true }))}>Active</button>
            <button className={!f.activeOnly ? "on" : ""} onClick={() => setF((s) => ({ ...s, activeOnly: false }))}>All</button>
          </div></div>
        <div className="fld"><span>Chart type</span>
          <div className="seg">{MODES.map(([m, l]) => <button key={m} className={mode === m ? "on" : ""} onClick={() => setMode(m)}>{l}</button>)}</div></div>
        <button className="reset" onClick={() => setF(EMPTY)}>Reset</button>
      </div>
      {active.length > 0 && (
        <div className="active-f">Filtered by: {active.map(([key, v]) => (
          <button key={key} onClick={() => set(key)("All")}>{key}: {v} ×</button>))}
          <span className="muted"> · tip: click any bar or slice to filter</span></div>
      )}

      <div className="tiles">
        <Tile label="Projects" value={fmtInt(k.total)} sub={`${k.active} active · ${k.analyzed} analyzed`} />
        <Tile label="Overall Red" value={fmtPct(k.redPct)} sub={`${k.red} of ${k.analyzed} analyzed`} tone="red" />
        <Tile label="Aggregate CPI" value={fmtNum(k.cpi)} sub={`median ${fmtNum(k.cpiMedian)} · ≥ 0.95 on budget`}
              tone={k.cpi == null ? "" : k.cpi >= 0.95 ? "green" : k.cpi >= 0.85 ? "amber" : "red"} />
        <Tile label="Budget used" value={fmtPct(k.budgetUsed)} sub={`${fmtMoney(k.actual)} of ${fmtMoney(k.planned)}`} />
        <Tile label="Past planned end" value={fmtInt(k.overdue)} sub="analyzed projects still open" tone={k.overdue ? "amber" : ""} />
        <Tile label="Optimistic reports" value={fmtInt(k.optimistic)} sub="PM declares better than calculated" tone={k.optimistic ? "amber" : ""} />
        <Tile label="Data-quality issues" value={fmtInt(k.dq)} sub="projects with ≥ 1 finding" tone={k.dq ? "amber" : ""} />
      </div>

      {rows.length === 0 ? <div className="center small">No projects match the filters.</div> : (
        <main className="grid-cards">
          <h2 className="sec">Health</h2>
          <Card kpi="KPIs 1–5" title="Calculated health by KPI" sub="Share of analyzed projects per status · donut = totals across the five KPIs" wide>
            <StackedChart data={healthDistribution(rows, KPI_HEALTH)} keys={STATUS_ORDER} colors={STATUS} mode={mode} percent nameWidth={110} />
          </Card>
          <Card kpi="KPI 1" title="Declared vs calculated overall" sub="Does the PM's report match the calculation?">
            <DistChart data={countBy(rows.filter((p) => p.analyzed), (p) => p.health.overall.cmp)} mode={mode}
                       colorFor={(n) => CMP[n]} />
          </Card>
          <Card kpi="KPI 1" title="Overall health by portfolio" sub="Click a bar to filter">
            <StackedChart data={healthByGroup(rows, "portfolio", 12)} keys={HEALTH_KEYS} colors={HEALTH_COLORS} mode={mode}
                          onSelect={toggle("portfolio")} nameWidth={80} />
          </Card>

          <h2 className="sec">Performance</h2>
          <Card kpi="KPI 6" title="Progress: actual vs expected" sub="Below the dashed line = behind schedule · click a dot for details" wide>
            <ProgressScatter projects={rows} onPick={setPick} />
          </Card>
          <Card kpi="KPIs 11–12" title="Cost performance (CPI) by portfolio" sub="EV / AC · dashed line = 1.00 · donut = projects by CPI band">
            <CpiChart groups={byGroupFinance(rows, "portfolio")} projects={rows.filter((p) => p.analyzed)} mode={mode} onSelect={toggle("portfolio")} />
          </Card>
          <Card kpi="KPIs 11–12" title="Planned vs actual cost by portfolio" sub="Top 12 by planned budget · donut = actual spend share">
            <CompareChart data={byGroupFinance(rows, "portfolio")} a={{ key: "planned", label: "Planned cost" }}
                          b={{ key: "actual", label: "Actual cost" }} fmt={fmtMoney} mode={mode} onSelect={toggle("portfolio")} />
          </Card>
          <Card kpi="KPI 13" title="Planned vs actual effort by portfolio" sub="Hours · donut = actual effort share">
            <CompareChart data={byGroupFinance(rows, "portfolio")} a={{ key: "pEff", label: "Planned effort (h)" }}
                          b={{ key: "aEff", label: "Actual effort (h)" }} fmt={(v) => `${fmtInt(v)} h`} mode={mode} onSelect={toggle("portfolio")} />
          </Card>
          <Card kpi="KPIs 7–10" title="Schedule dates status" sub="Analyzed projects by planned-end situation">
            <DistChart mode={mode} colorFor={(n) => ({ "On time": STATUS.Green, "Past planned end": STATUS.Red, "Not started": "#A7AEBB" }[n])}
                       data={countBy(rows.filter((p) => p.analyzed), (p) => (p.overdue ? "Past planned end" : p.actualStart ? "On time" : "Not started"))} />
          </Card>

          <h2 className="sec">Control</h2>
          <Card kpi="KPIs 14–19" title="Open control items" sub="Sum across analyzed projects">
            <DistChart data={controlTotals(rows)} mode={mode} colorFor={(n, i) => [STATUS.Red, STATUS.Red, SERIES[1], SERIES[0], STATUS.Red, SERIES[2]][i % 6]} />
          </Card>
          <Card kpi="KPI 14" title="Milestones" sub="Completed vs pending vs overdue">
            <DistChart data={milestoneStatus(rows)} mode={mode}
                       colorFor={(n) => ({ Completed: STATUS.Green, "Pending (on time)": SERIES[0], Overdue: STATUS.Red }[n])} />
          </Card>

          <h2 className="sec">Breakdown</h2>
          <Card title="Projects by category" sub="Click to filter">
            <DistChart data={countBy(rows, "category")} mode={mode} colorFor={() => SERIES[0]} onSelect={toggle("category")} />
          </Card>
          <Card title="Projects by region" sub="Custom field u_region · click to filter">
            <DistChart data={countBy(rows, "region")} mode={mode} onSelect={toggle("region")} fold
                       colorFor={(n, i) => (mode === "donut" ? DONUT5[i] || "#A7AEBB" : SERIES[0])} />
          </Card>
          <Card title="Overall health by program" sub="Top 15 programs by number of projects · click to filter" wide>
            <StackedChart data={healthByGroup(rows, "program", 15)} keys={HEALTH_KEYS} colors={HEALTH_COLORS} mode={mode}
                          onSelect={toggle("program")} nameWidth={80} />
          </Card>

          <h2 className="sec">Data quality</h2>
          <Card title="Projects with data-quality findings" sub="By rule · color = severity (High / Medium / Low)" wide>
            <DistChart data={dqByRule(rows, data.dqRules)} mode={mode} colorFor={(n) => SEVERITY[data.dqRules[n.split(" ")[0]]?.severity] || SERIES[0]} />
            <div className="legend-inline">{Object.entries(SEVERITY).map(([s, c]) => <span key={s}><i style={{ background: c }} />{s}</span>)}</div>
          </Card>

          <h2 className="sec">Projects</h2>
          <Card title="Project list" sub="Click a column to sort · click a row for all 19 KPIs" wide>
            <ProjectTable rows={rows} onPick={setPick} />
          </Card>
        </main>
      )}
      <footer>Source: {data.source}. Health thresholds are configurable assumptions; expected progress is linear.
        Colors: PepsiCo-inspired palette; status colors are always paired with labels.</footer>
      <Drawer p={picked} onClose={() => setPick(null)} />
    </div>
  );
}

function lastDbQuery(data) {
  const iso = data.lastDbQuery || data.generatedAt;
  try {
    return new Date(iso).toLocaleString("en-CA", { timeZone: "America/Mexico_City", hour12: false,
      year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).replace(",", "");
  } catch {
    return String(iso).replace("T", " ").slice(0, 16);
  }
}
