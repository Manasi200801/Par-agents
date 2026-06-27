"use client";

import { useEffect, useRef, useState } from "react";
import type { ReplayCycle } from "@/lib/replay-data";

const SERIES = [
  { key: "mae_machine", label: "System forecast", color: "var(--color-ink-3)", width: 1.5, dash: "5 4" },
  { key: "mae_planner", label: "Planner alone", color: "var(--color-caution)", width: 2, dash: "" },
  { key: "mae_compass", label: "Planner + Compass", color: "var(--color-support)", width: 2.75, dash: "" },
] as const;

const H = 300;
const PAD = { l: 46, r: 16, t: 18, b: 30 };

function niceBounds(min: number, max: number) {
  const lo = Math.floor(min / 250) * 250;
  const hi = Math.ceil(max / 250) * 250;
  return [lo, hi] as const;
}

function monthLabel(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("en", { month: "short", year: "2-digit" });
}

export function ReplayChart({ data }: { data: ReplayCycle[] }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(760);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => setW(entries[0].contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const n = data.length;
  const allVals = data.flatMap((d) => [d.mae_machine, d.mae_planner, d.mae_compass]);
  const [yLo, yHi] = niceBounds(Math.min(...allVals), Math.max(...allVals));

  const plotW = w - PAD.l - PAD.r;
  const plotH = H - PAD.t - PAD.b;
  const x = (i: number) => PAD.l + (n <= 1 ? 0 : (i / (n - 1)) * plotW);
  const y = (v: number) => PAD.t + (1 - (v - yLo) / (yHi - yLo)) * plotH;

  const path = (key: (typeof SERIES)[number]["key"]) =>
    data.map((d, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)} ${y(d[key]).toFixed(1)}`).join(" ");

  const yTicks = 4;
  const ticks = Array.from({ length: yTicks + 1 }, (_, i) => yLo + ((yHi - yLo) * i) / yTicks);
  const xEvery = Math.ceil(n / 6);

  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const i = Math.round(((mx - PAD.l) / plotW) * (n - 1));
    setHover(Math.max(0, Math.min(n - 1, i)));
  }

  const hv = hover != null ? data[hover] : null;

  return (
    <div ref={wrapRef} className="w-full">
      <svg
        width={w}
        height={H}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        style={{ display: "block", touchAction: "none" }}
      >
        {/* y gridlines + labels */}
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={PAD.l} x2={w - PAD.r} y1={y(t)} y2={y(t)} stroke="var(--color-line-soft)" strokeWidth={1} />
            <text x={PAD.l - 8} y={y(t) + 3.5} textAnchor="end" fontSize={10.5} fill="var(--color-ink-4)" className="tnum">
              {Math.round(t)}
            </text>
          </g>
        ))}

        {/* x labels */}
        {data.map((d, i) =>
          i % xEvery === 0 ? (
            <text key={i} x={x(i)} y={H - 10} textAnchor="middle" fontSize={10.5} fill="var(--color-ink-4)">
              {monthLabel(d.cutoff_date)}
            </text>
          ) : null
        )}

        {/* hover guide */}
        {hv && (
          <line x1={x(hover!)} x2={x(hover!)} y1={PAD.t} y2={H - PAD.b} stroke="var(--color-line-strong)" strokeWidth={1} />
        )}

        {/* series */}
        {SERIES.map((s) => (
          <path
            key={s.key}
            d={path(s.key)}
            fill="none"
            stroke={s.color}
            strokeWidth={s.width}
            strokeDasharray={s.dash || undefined}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}

        {/* hover dots */}
        {hv &&
          SERIES.map((s) => (
            <circle key={s.key} cx={x(hover!)} cy={y(hv[s.key])} r={3.5} fill="var(--color-panel)" stroke={s.color} strokeWidth={2} />
          ))}
      </svg>

      {/* legend */}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 mt-1 px-1">
        {SERIES.map((s) => (
          <span key={s.key} className="inline-flex items-center gap-2 text-[12px] text-ink-2">
            <span style={{ width: 16, height: 0, borderTop: `${s.width}px ${s.dash ? "dashed" : "solid"} ${s.color}`, display: "inline-block" }} />
            {s.label}
          </span>
        ))}
      </div>

      {/* hover readout */}
      <div className="mt-3 h-[44px]">
        {hv ? (
          <div className="inline-flex flex-wrap items-center gap-x-5 gap-y-1 card px-3.5 py-2 text-[12.5px]">
            <span className="text-ink-3">{monthLabel(hv.cutoff_date)} cycle</span>
            {SERIES.map((s) => (
              <span key={s.key} className="inline-flex items-center gap-1.5 tnum">
                <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
                <span className="text-ink-3">{s.label.split(" ").pop()}</span>
                <span className="text-ink font-medium">{hv[s.key]}</span>
              </span>
            ))}
            <span className="text-ink-4 tnum">· {Math.round(hv.pct_helped * 100)}% of changes helped</span>
          </div>
        ) : (
          <div className="text-[12px] text-ink-4 px-1 pt-1">Hover the chart to read each cycle. Lower error is better.</div>
        )}
      </div>
    </div>
  );
}
