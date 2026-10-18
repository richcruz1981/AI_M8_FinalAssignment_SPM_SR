import React from "react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, PieChart, Pie, Cell,
  LabelList, ScatterChart, Scatter, ReferenceLine, ZAxis,
} from "recharts";
import { UI, SERIES, STATUS } from "../theme.js";

const axis = { stroke: UI.grid, tick: { fill: UI.ink2, fontSize: 12 }, tickLine: false };
const legendStyle = { fontSize: 12, color: UI.ink2, paddingBottom: 6 };
// Legend text stays in neutral ink (the swatch carries identity, never the text color).
const legendFmt = (v) => <span style={{ color: UI.ink2 }}>{v}</span>;

export function TooltipBox({ active, payload, label, fmt = (v) => v, title }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="tip">
      <div className="tip-title">{title || label || payload[0]?.payload?.name}</div>
      {payload.map((p) => (
        <div key={p.dataKey + p.name} className="tip-row">
          <span className="sw" style={{ background: p.color || p.payload?.fill }} />
          <span>{p.name}</span>
          <b>{fmt(p.value, p)}</b>
        </div>
      ))}
    </div>
  );
}

// Five validated slots for donuts (brand blue, tangelo, electric blue, violet, magenta), then "Other".
export const DONUT5 = ["#3D63C4", "#EB7B30", "#0096D6", "#6250D6", "#E87BA4"];
const heightFor = (n, mode) => (mode === "bars" ? Math.max(220, 34 * n + 70) : 300);

/** Single-series distribution: bars (horizontal) · columns · donut. colorFor(name, i) -> color */
const OTHER = "#A7AEBB";
// Donut never cycles hues: keep the top slices and fold the rest into "Other".
function foldTop(data, n = 5) {
  if (data.length <= n + 1) return data;
  const s = [...data].sort((a, b) => b.value - a.value);
  return [...s.slice(0, n), { name: "Other", value: s.slice(n).reduce((a, d) => a + d.value, 0) }];
}

export function DistChart({ data: raw, mode, colorFor = () => SERIES[0], onSelect, fmt = (v) => v, total, height, fold = false }) {
  const data = mode === "donut" && fold ? foldTop(raw) : raw;
  const tot = total ?? data.reduce((a, d) => a + d.value, 0);
  const lbl = (v) => `${fmt(v)}${tot ? ` · ${Math.round((100 * v) / tot)}%` : ""}`;
  const click = (d) => onSelect && onSelect(d.name ?? d.payload?.name);
  if (mode === "donut") {
    return (
      <ResponsiveContainer width="100%" height={height || 300}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius="55%" outerRadius="82%" paddingAngle={1.5}
               stroke={UI.card} strokeWidth={2} onClick={click} cursor={onSelect ? "pointer" : "default"}
               animationDuration={600}
               label={({ value, x, y, textAnchor }) => (tot && value / tot >= 0.05
                 ? <text x={x} y={y} textAnchor={textAnchor} dominantBaseline="central" fill={UI.ink} fontSize={12} fontWeight={600}>
                     {`${Math.round((100 * value) / tot)}%`}</text> : null)}
               labelLine={false}>
            {data.map((d, i) => <Cell key={d.name} fill={d.name === "Other" ? OTHER : colorFor(d.name, i)} />)}
          </Pie>
          <Tooltip content={<TooltipBox fmt={(v) => lbl(v)} />} />
          <Legend wrapperStyle={legendStyle} iconType="circle" formatter={legendFmt} />
        </PieChart>
      </ResponsiveContainer>
    );
  }
  const horizontal = mode === "bars";
  return (
    <ResponsiveContainer width="100%" height={height || heightFor(data.length, mode)}>
      <BarChart data={data} layout={horizontal ? "vertical" : "horizontal"}
                margin={{ top: 18, right: horizontal ? 70 : 12, left: 8, bottom: horizontal ? 4 : 40 }}>
        <CartesianGrid stroke={UI.grid} horizontal={!horizontal} vertical={horizontal} />
        {horizontal ? (
          <>
            <XAxis type="number" allowDecimals={false} {...axis} />
            <YAxis type="category" dataKey="name" width={170} {...axis} tick={{ fill: UI.ink, fontSize: 12 }} />
          </>
        ) : (
          <>
            <XAxis dataKey="name" interval={0} angle={data.length > 6 ? -30 : 0} textAnchor={data.length > 6 ? "end" : "middle"}
                   height={data.length > 6 ? 70 : 30} {...axis} tick={{ fill: UI.ink, fontSize: 11 }} />
            <YAxis allowDecimals={false} {...axis} />
          </>
        )}
        <Tooltip cursor={{ fill: "rgba(40,69,142,0.06)" }} content={<TooltipBox fmt={(v) => lbl(v)} />} />
        <Bar dataKey="value" name="Projects" radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]} maxBarSize={36}
             onClick={click} cursor={onSelect ? "pointer" : "default"}>
          {data.map((d, i) => <Cell key={d.name} fill={colorFor(d.name, i)} />)}
          <LabelList dataKey="value" position={horizontal ? "right" : "top"} formatter={lbl}
                     style={{ fill: UI.ink, fontSize: 11 }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Multi-series stacked: bars · columns · donut (donut = totals per series). */
export function StackedChart({ data, keys, colors, mode, onSelect, percent = false, nameWidth = 110, height }) {
  if (mode === "donut") {
    const totals = keys.map((k) => ({ name: k, value: data.reduce((a, d) => a + (d[k] || 0), 0) })).filter((d) => d.value);
    return <DistChart data={totals} mode="donut" colorFor={(n) => colors[n]} height={height} />;
  }
  const horizontal = mode === "bars";
  const rows = percent
    ? data.map((d) => {
        const t = keys.reduce((a, k) => a + (d[k] || 0), 0) || 1;
        const o = { ...d };
        keys.forEach((k) => (o[`${k}__raw`] = d[k] || 0, o[k] = +((100 * (d[k] || 0)) / t).toFixed(1)));
        return o;
      })
    : data;
  const fmt = (v, p) => (percent ? `${p?.payload?.[`${p.dataKey}__raw`] ?? ""} (${v}%)` : v);
  return (
    <ResponsiveContainer width="100%" height={height || heightFor(data.length, mode)}>
      <BarChart data={rows} layout={horizontal ? "vertical" : "horizontal"}
                margin={{ top: 8, right: 24, left: 8, bottom: horizontal ? 4 : 40 }}>
        <CartesianGrid stroke={UI.grid} horizontal={!horizontal} vertical={horizontal} />
        {horizontal ? (
          <>
            <XAxis type="number" domain={percent ? [0, 100] : [0, "auto"]} allowDecimals={false} allowDataOverflow={percent}
                   ticks={percent ? [0, 25, 50, 75, 100] : undefined} tickFormatter={(v) => (percent ? `${v}%` : v)} {...axis} />
            <YAxis type="category" dataKey="name" width={nameWidth} {...axis} tick={{ fill: UI.ink, fontSize: 12 }} />
          </>
        ) : (
          <>
            <XAxis dataKey="name" interval={0} angle={data.length > 6 ? -30 : 0} textAnchor={data.length > 6 ? "end" : "middle"}
                   height={data.length > 6 ? 70 : 30} {...axis} tick={{ fill: UI.ink, fontSize: 11 }} />
            <YAxis domain={percent ? [0, 100] : [0, "auto"]} allowDecimals={false} allowDataOverflow={percent}
                   ticks={percent ? [0, 25, 50, 75, 100] : undefined} tickFormatter={(v) => (percent ? `${v}%` : v)} {...axis} />
          </>
        )}
        <Tooltip cursor={{ fill: "rgba(40,69,142,0.06)" }} content={<TooltipBox fmt={fmt} />} />
        <Legend verticalAlign="top" wrapperStyle={legendStyle} iconType="square" formatter={legendFmt} />
        {keys.map((k, i) => (
          <Bar key={k} dataKey={k} stackId="s" fill={colors[k]} stroke={UI.card} strokeWidth={1.5} maxBarSize={34}
               onClick={(d) => onSelect && onSelect(d.name)} cursor={onSelect ? "pointer" : "default"}
               radius={i === keys.length - 1 ? (horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]) : 0}>
            <LabelList dataKey={percent ? `${k}__raw` : k}
                       content={({ x, y, width, height, value }) =>
                         value && (horizontal ? width : height) >= 16 && (horizontal ? height : width) >= 14 ? (
                           <text x={x + width / 2} y={y + height / 2} textAnchor="middle" dominantBaseline="central" fontSize={11}
                                 fontWeight={600} fill={["Amber", "No data", "Not analyzed"].includes(k) ? UI.ink : "#fff"}>{value}</text>
                         ) : null} />
          </Bar>
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Two-measure comparison per group (planned vs actual): grouped bars · columns · donut of the 2nd measure. */
export function CompareChart({ data, a, b, fmt, mode, onSelect }) {
  if (mode === "donut") {
    return <DistChart data={data.map((d) => ({ name: d.name, value: d[b.key] }))} mode="donut" fold
                      colorFor={(n, i) => DONUT5[i] || OTHER} fmt={fmt} />;
  }
  const horizontal = mode === "bars";
  return (
    <ResponsiveContainer width="100%" height={horizontal ? Math.max(240, 44 * data.length + 70) : 320}>
      <BarChart data={data} layout={horizontal ? "vertical" : "horizontal"}
                margin={{ top: 8, right: 24, left: 8, bottom: horizontal ? 4 : 40 }}>
        <CartesianGrid stroke={UI.grid} horizontal={!horizontal} vertical={horizontal} />
        {horizontal ? (
          <>
            <XAxis type="number" tickFormatter={fmt} {...axis} />
            <YAxis type="category" dataKey="name" width={80} {...axis} tick={{ fill: UI.ink, fontSize: 12 }} />
          </>
        ) : (
          <>
            <XAxis dataKey="name" interval={0} angle={data.length > 6 ? -30 : 0} textAnchor={data.length > 6 ? "end" : "middle"}
                   height={data.length > 6 ? 70 : 30} {...axis} tick={{ fill: UI.ink, fontSize: 11 }} />
            <YAxis tickFormatter={fmt} {...axis} />
          </>
        )}
        <Tooltip cursor={{ fill: "rgba(40,69,142,0.06)" }} content={<TooltipBox fmt={(v) => fmt(v)} />} />
        <Legend verticalAlign="top" wrapperStyle={legendStyle} iconType="square" formatter={legendFmt} />
        <Bar dataKey={a.key} name={a.label} fill={SERIES[0]} radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]} maxBarSize={18}
             onClick={(d) => onSelect && onSelect(d.name)} cursor={onSelect ? "pointer" : "default"} />
        <Bar dataKey={b.key} name={b.label} fill={SERIES[1]} radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]} maxBarSize={18}
             onClick={(d) => onSelect && onSelect(d.name)} cursor={onSelect ? "pointer" : "default"} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/** CPI per group with the 1.0 reference; donut mode = projects by CPI band. */
export function CpiChart({ groups, projects, mode, onSelect }) {
  if (mode === "donut") {
    const p = projects.filter((x) => x.cpi != null);
    const bands = [
      { name: "CPI ≥ 0.95 (on budget)", value: p.filter((x) => x.cpi >= 0.95).length, c: STATUS.Green },
      { name: "0.85 – 0.95 (watch)", value: p.filter((x) => x.cpi >= 0.85 && x.cpi < 0.95).length, c: STATUS.Amber },
      { name: "CPI < 0.85 (overrun)", value: p.filter((x) => x.cpi < 0.85).length, c: STATUS.Red },
    ].filter((b) => b.value);
    return <DistChart data={bands} mode="donut" colorFor={(n) => bands.find((b) => b.name === n).c} />;
  }
  const horizontal = mode === "bars";
  const data = groups.filter((g) => g.cpi != null);
  const col = (v) => (v >= 0.95 ? STATUS.Green : v >= 0.85 ? STATUS.Amber : STATUS.Red);
  return (
    <ResponsiveContainer width="100%" height={horizontal ? Math.max(240, 34 * data.length + 60) : 300}>
      <BarChart data={data} layout={horizontal ? "vertical" : "horizontal"}
                margin={{ top: 18, right: 50, left: 8, bottom: horizontal ? 4 : 40 }}>
        <CartesianGrid stroke={UI.grid} horizontal={!horizontal} vertical={horizontal} />
        {horizontal ? (
          <>
            <XAxis type="number" domain={[0, 1.25]} ticks={[0, 0.25, 0.5, 0.75, 1, 1.25]} {...axis} />
            <YAxis type="category" dataKey="name" width={80} {...axis} tick={{ fill: UI.ink, fontSize: 12 }} />
            <ReferenceLine x={1} stroke={UI.ink2} strokeDasharray="4 4" label={{ value: "1.00", fill: UI.ink2, fontSize: 11, position: "top" }} />
          </>
        ) : (
          <>
            <XAxis dataKey="name" interval={0} angle={data.length > 6 ? -30 : 0} textAnchor={data.length > 6 ? "end" : "middle"}
                   height={data.length > 6 ? 70 : 30} {...axis} tick={{ fill: UI.ink, fontSize: 11 }} />
            <YAxis domain={[0, 1.25]} ticks={[0, 0.25, 0.5, 0.75, 1, 1.25]} {...axis} />
            <ReferenceLine y={1} stroke={UI.ink2} strokeDasharray="4 4" />
          </>
        )}
        <Tooltip cursor={{ fill: "rgba(40,69,142,0.06)" }} content={<TooltipBox fmt={(v) => v.toFixed(2)} />} />
        <Bar dataKey="cpi" name="Aggregate CPI" maxBarSize={30} radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]}
             onClick={(d) => onSelect && onSelect(d.name)} cursor={onSelect ? "pointer" : "default"}>
          {data.map((d) => <Cell key={d.name} fill={col(d.cpi)} />)}
          <LabelList dataKey="cpi" position={horizontal ? "right" : "top"} formatter={(v) => v.toFixed(2)}
                     style={{ fill: UI.ink, fontSize: 11 }} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** % complete: actual vs expected, one dot per project, colored by calculated overall health. */
export function ProgressScatter({ projects, onPick }) {
  const groups = ["Green", "Amber", "Red", "No data"].map((s) => ({
    s, data: projects.filter((p) => p.analyzed && p.pctExpected != null && p.health.overall.calc === s)
      .map((p) => ({ x: p.pctExpected, y: p.pctComplete, id: p.id, name: p.name, gap: p.gapPp })),
  })).filter((g) => g.data.length);
  return (
    <ResponsiveContainer width="100%" height={320}>
      <ScatterChart margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
        <CartesianGrid stroke={UI.grid} />
        <XAxis type="number" dataKey="x" name="Expected" domain={[0, 100]} unit="%" {...axis}
               label={{ value: "Expected % complete (linear)", position: "insideBottom", offset: -10, fill: UI.ink2, fontSize: 12 }} />
        <YAxis type="number" dataKey="y" name="Actual" domain={[0, 100]} unit="%" {...axis}
               label={{ value: "Actual %", angle: -90, position: "insideLeft", fill: UI.ink2, fontSize: 12 }} />
        <ZAxis range={[70, 70]} />
        <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 100, y: 100 }]} stroke={UI.ink2} strokeDasharray="4 4" />
        <Tooltip content={({ active, payload }) => active && payload?.length ? (
          <div className="tip"><div className="tip-title">{payload[0].payload.id}</div>
            <div className="tip-sub">{payload[0].payload.name}</div>
            <div className="tip-row"><span>Actual</span><b>{payload[0].payload.y}%</b></div>
            <div className="tip-row"><span>Expected</span><b>{payload[0].payload.x}%</b></div>
            <div className="tip-row"><span>Gap</span><b>{payload[0].payload.gap} pp</b></div></div>) : null} />
        <Legend verticalAlign="top" wrapperStyle={legendStyle} iconType="circle" formatter={legendFmt} />
        {groups.map((g) => (
          <Scatter key={g.s} name={g.s} data={g.data} fill={STATUS[g.s]} stroke={UI.card} strokeWidth={1.5}
                   onClick={(d) => onPick && onPick(d.id)} cursor="pointer" />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  );
}
