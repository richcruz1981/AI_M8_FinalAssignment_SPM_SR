import { STATUS_ORDER } from "./theme.js";

export const fmtInt = (v) => (v == null ? "—" : Math.round(v).toLocaleString("en-US"));
export const fmtMoney = (v) =>
  v == null ? "—" : v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `$${(v / 1e3).toFixed(0)}K` : `$${v.toFixed(0)}`;
export const fmtPct = (v, d = 0) => (v == null ? "—" : `${Number(v).toFixed(d)}%`);
export const fmtNum = (v, d = 2) => (v == null ? "—" : Number(v).toFixed(d));

export const sum = (xs, f) => xs.reduce((a, x) => a + (f(x) ?? 0), 0);
export function median(xs) {
  const s = xs.filter((x) => x != null).sort((a, b) => a - b);
  if (!s.length) return null;
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export function applyFilters(projects, f) {
  const q = f.search.trim().toLowerCase();
  return projects.filter(
    (p) =>
      (!f.activeOnly || p.active) &&
      (f.portfolio === "All" || p.portfolio === f.portfolio) &&
      (f.program === "All" || p.program === f.program) &&
      (f.region === "All" || p.region === f.region) &&
      (f.category === "All" || p.category === f.category) &&
      (f.pm === "All" || p.pm === f.pm) &&
      (f.health === "All" || (p.analyzed ? p.health.overall.calc : "Not analyzed") === f.health) &&
      (!q || p.id.toLowerCase().includes(q) || (p.name || "").toLowerCase().includes(q))
  );
}

export const countBy = (rows, key) => {
  const m = new Map();
  rows.forEach((r) => {
    const k = typeof key === "function" ? key(r) : r[key];
    m.set(k, (m.get(k) || 0) + 1);
  });
  return [...m.entries()].map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
};

// Group → stacked health counts (only analyzed projects carry health)
export function healthByGroup(rows, key, top = 15) {
  const m = new Map();
  rows.forEach((p) => {
    const g = p[key];
    if (!m.has(g)) m.set(g, { name: g, total: 0, Green: 0, Amber: 0, Red: 0, "No data": 0, "Not analyzed": 0 });
    const o = m.get(g);
    o.total += 1;
    if (p.analyzed) o[p.health.overall.calc] += 1;
    else o["Not analyzed"] += 1;
  });
  return [...m.values()].sort((a, b) => b.total - a.total || String(a.name).localeCompare(b.name)).slice(0, top);
}

export function healthDistribution(rows, kpis) {
  const a = rows.filter((p) => p.analyzed);
  return kpis.map(([k, label]) => {
    const o = { name: label, key: k };
    STATUS_ORDER.forEach((s) => (o[s] = a.filter((p) => p.health[k].calc === s).length));
    return o;
  });
}

export function kpiSummary(rows) {
  const a = rows.filter((p) => p.analyzed);
  const withCpi = a.filter((p) => p.cpi != null && p.actualCost);
  const ev = sum(withCpi, (p) => p.earnedValue);
  const ac = sum(withCpi, (p) => p.actualCost);
  const planned = sum(a, (p) => p.plannedCost);
  const actual = sum(a, (p) => p.actualCost);
  const red = a.filter((p) => p.health.overall.calc === "Red").length;
  return {
    total: rows.length,
    active: rows.filter((p) => p.active).length,
    analyzed: a.length,
    red,
    redPct: a.length ? (100 * red) / a.length : null,
    cpi: ac ? ev / ac : null,
    cpiMedian: median(withCpi.map((p) => p.cpi)),
    planned,
    actual,
    budgetUsed: planned ? (100 * actual) / planned : null,
    overdue: a.filter((p) => p.overdue).length,
    dq: rows.filter((p) => p.dq.length).length,
    optimistic: a.filter((p) => p.health.overall.cmp === "Optimistic").length,
  };
}

export function byGroupFinance(rows, key, top = 12) {
  const m = new Map();
  rows.filter((p) => p.analyzed).forEach((p) => {
    const g = p[key];
    if (!m.has(g)) m.set(g, { name: g, planned: 0, actual: 0, ev: 0, acCpi: 0, pEff: 0, aEff: 0, n: 0 });
    const o = m.get(g);
    o.n += 1;
    o.planned += p.plannedCost || 0;
    o.actual += p.actualCost || 0;
    o.pEff += p.plannedEffort || 0;
    o.aEff += p.actualEffort || 0;
    if (p.cpi != null && p.actualCost) {
      o.ev += p.earnedValue || 0;
      o.acCpi += p.actualCost;
    }
  });
  return [...m.values()]
    .map((o) => ({ ...o, cpi: o.acCpi ? +(o.ev / o.acCpi).toFixed(2) : null }))
    .sort((a, b) => b.planned - a.planned)
    .slice(0, top);
}

export function controlTotals(rows) {
  const a = rows.filter((p) => p.analyzed);
  return [
    { name: "14 · Overdue milestones", value: sum(a, (p) => p.milestonesOverdue) },
    { name: "15 · High open risks", value: sum(a, (p) => p.risksHigh) },
    { name: "16 · Open issues", value: sum(a, (p) => p.issuesOpen) },
    { name: "17 · Pending decisions", value: sum(a, (p) => p.decisionsPending) },
    { name: "18 · Overdue actions", value: sum(a, (p) => p.actionsOverdue) },
    { name: "19 · Pending changes", value: sum(a, (p) => p.changesPending) },
  ];
}

export function milestoneStatus(rows) {
  const a = rows.filter((p) => p.analyzed);
  const total = sum(a, (p) => p.milestonesTotal);
  const done = sum(a, (p) => p.milestonesDone);
  const overdue = sum(a, (p) => p.milestonesOverdue);
  return [
    { name: "Completed", value: done, color: "Green" },
    { name: "Pending (on time)", value: Math.max(0, total - done - overdue), color: "series0" },
    { name: "Overdue", value: overdue, color: "Red" },
  ];
}

export function dqByRule(rows, rules) {
  const m = new Map();
  rows.forEach((p) => p.dq.forEach((r) => m.set(r, (m.get(r) || 0) + 1)));
  return [...m.entries()]
    .map(([rule, value]) => ({ rule, name: `${rule} ${rules[rule]?.label || ""}`, value, severity: rules[rule]?.severity }))
    .sort((a, b) => b.value - a.value);
}
