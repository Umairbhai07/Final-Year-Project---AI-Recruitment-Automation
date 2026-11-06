import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHART } from "../lib/format";

const tick = { fontSize: 11, fill: CHART.axis };
const tooltipStyle = { borderRadius: 8, border: `1px solid ${CHART.grid}`, fontSize: 12, boxShadow: "0 4px 12px rgba(15,23,42,.08)" };

/** Horizontal bars with the value printed at the end, e.g. a funnel or "most missing skills". */
export function HBars({ data, color = CHART.brand, max, suffix = "", empty = "No data yet" }: {
  data: { label: string; value: number; color?: string }[];
  color?: string;
  max?: number;
  suffix?: string;
  empty?: string;
}) {
  if (!data.length) return <p className="py-6 text-center text-sm text-slate-400">{empty}</p>;
  const top = max ?? Math.max(1, ...data.map((d) => d.value));
  return (
    <ul className="space-y-2.5">
      {data.map((d) => (
        <li key={d.label}>
          <div className="mb-1 flex justify-between gap-3 text-xs">
            <span className="truncate text-slate-600">{d.label}</span>
            <span className="font-semibold tabular-nums text-slate-900">{d.value}{suffix}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full transition-all duration-500" style={{ width: `${Math.max(d.value ? 2 : 0, (d.value / top) * 100)}%`, background: d.color ?? color }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Vertical bar chart (score histogram, per-question scores). */
export function VBars({ data, x, y, height = 200, color = CHART.brand, yMax, name = "Value", colorFor }: {
  data: Record<string, unknown>[];
  x: string;
  y: string;
  height?: number;
  color?: string;
  yMax?: number;
  name?: string;
  colorFor?: (row: Record<string, unknown>) => string;
}) {
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 6, right: 4, left: -22, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={CHART.grid} />
          <XAxis dataKey={x} tick={tick} tickLine={false} axisLine={{ stroke: CHART.grid }} interval={0} />
          <YAxis allowDecimals={false} tick={tick} tickLine={false} axisLine={false} domain={yMax ? [0, yMax] : undefined} />
          <Tooltip cursor={{ fill: "#f1f5f9" }} contentStyle={tooltipStyle} formatter={(v) => [v, name]} />
          <Bar dataKey={y} fill={color} radius={[4, 4, 0, 0]} maxBarSize={36}>
            {colorFor && data.map((row, i) => <Cell key={i} fill={colorFor(row)} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Donut with a legend beside it. */
export function Donut({ data, center, size = 140 }: {
  data: { label: string; value: number; color: string }[];
  center?: string;
  size?: number;
}) {
  const total = data.reduce((n, d) => n + d.value, 0);
  if (!total) return <p className="py-6 text-center text-sm text-slate-400">No data yet</p>;
  return (
    <div className="flex items-center gap-5">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="label" innerRadius="62%" outerRadius="100%" paddingAngle={data.filter((d) => d.value).length > 1 ? 2 : 0} stroke="none" isAnimationActive={false}>
              {data.map((d) => <Cell key={d.label} fill={d.color} />)}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-bold tabular-nums text-slate-900">{center ?? total}</span>
        </div>
      </div>
      <ul className="min-w-0 space-y-1.5 text-sm">
        {data.map((d) => (
          <li key={d.label} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: d.color }} />
            <span className="truncate text-slate-600">{d.label}</span>
            <span className="ml-auto pl-2 font-semibold tabular-nums text-slate-900">{d.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Funnel drawn as centred bars that narrow at each step, with the drop between steps. */
export function Funnel({ steps }: { steps: { label: string; count: number }[] }) {
  const top = Math.max(1, steps[0]?.count ?? 1);
  const shades = ["#e5e5e5", "#d4d4d4", "#a3a3a3", "#404040", "#0a0a0a"];
  return (
    <div className="space-y-1.5">
      {steps.map((s, i) => {
        const prev = steps[i - 1]?.count;
        const rate = prev ? Math.round((s.count / prev) * 100) : null;
        return (
          <div key={s.label} className="flex items-center gap-3">
            <span className="w-32 shrink-0 text-xs text-slate-600">{s.label}</span>
            <div className="relative h-7 flex-1">
              <div className="mx-auto flex h-full items-center justify-center rounded text-xs font-semibold text-white transition-all duration-500"
                style={{ width: `${Math.max(8, (s.count / top) * 100)}%`, background: shades[i % shades.length], color: i < 3 ? "#171717" : "#fff" }}>
                {s.count}
              </div>
            </div>
            <span className="w-12 shrink-0 text-right text-xs tabular-nums text-slate-400">{rate !== null ? `${rate}%` : ""}</span>
          </div>
        );
      })}
    </div>
  );
}

export const scoreColor = (v: number, max = 100) => {
  const pct = (v / max) * 100;
  return pct >= 70 ? "#0a0a0a" : pct >= 45 ? "#737373" : "#c4c4c4"; // darker = stronger
};
