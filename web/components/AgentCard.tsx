import type { Signal } from "@/lib/types";
import { DirectionGlyph } from "./icons";

const DIR = {
  supports_override: { label: "Supports", color: "var(--color-support)", tint: "rgba(76,183,130,0.10)" },
  contradicts_override: { label: "Cautions", color: "var(--color-caution)", tint: "rgba(226,163,60,0.10)" },
  neutral: { label: "Neutral", color: "var(--color-ink-3)", tint: "rgba(255,255,255,0.04)" },
} as const;

// Friendly names for the raw data tables, so the source reads in plain English.
const SOURCE: Record<string, string> = {
  future_order_book: "Order book",
  stock_on_hand: "Stock levels",
  cost_breakdown: "Cost & margin",
  price_changes: "Pricing & promotions",
  marketing_spends: "Marketing",
  purchase_orders: "Supplier orders",
  decisions: "Past decisions",
};

function Meter({ value, label }: { value: number; label: string }) {
  const filled = Math.round(value * 4); // 4-segment meter
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] uppercase tracking-wider text-ink-4 w-[58px]">{label}</span>
      <span className="seg" aria-label={`${label} ${Math.round(value * 100)}%`}>
        {[0, 1, 2, 3].map((i) => (
          <i key={i} style={i < filled ? { background: "var(--color-ink-2)" } : undefined} />
        ))}
      </span>
    </div>
  );
}

export function AgentCard({ signal, index }: { signal: Signal; index: number }) {
  const dir = DIR[signal.direction as keyof typeof DIR] ?? DIR.neutral;
  const hasRows = signal.evidence_rows && signal.evidence_rows.length > 0;

  return (
    <article
      className="card fade-up relative overflow-hidden p-4 pl-5"
      style={{ animationDelay: `${index * 90}ms` }}
    >
      <span className="accent" style={{ background: dir.color }} />

      <header className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-[15px] font-medium text-ink leading-tight">{signal.agent_name}</h3>
          <span className="text-[11px] text-ink-4">from {SOURCE[signal.table] ?? signal.table}</span>
        </div>
        <span
          className="inline-flex items-center gap-1.5 shrink-0 rounded-md px-2 py-1 text-[11px] font-medium"
          style={{ color: dir.color, background: dir.tint }}
        >
          <DirectionGlyph direction={signal.direction} size={12} />
          {dir.label}
        </span>
      </header>

      <p className="mt-2.5 text-[13.5px] leading-relaxed text-ink-2">{signal.claim}</p>

      <div className="mt-3.5 flex flex-col gap-1.5">
        <Meter value={signal.magnitude} label="Strength" />
        <Meter value={signal.confidence} label="Confidence" />
      </div>

      {hasRows && (
        <details className="mt-3 group">
          <summary className="cursor-pointer list-none text-[12px] text-ink-3 hover:text-ink-2 transition-colors select-none">
            <span className="inline-block transition-transform group-open:rotate-90">›</span>{" "}
            {signal.evidence_rows.length} data point
            {signal.evidence_rows.length > 1 ? "s" : ""}
          </summary>
          <div className="mt-2 overflow-x-auto rounded-md border border-line">
            <table className="w-full text-[11.5px] tnum">
              <thead>
                <tr className="text-ink-4 text-left">
                  {Object.keys(signal.evidence_rows[0]).map((k) => (
                    <th key={k} className="font-medium px-2.5 py-1.5 border-b border-line-soft whitespace-nowrap">{k}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {signal.evidence_rows.map((row, i) => (
                  <tr key={i} className="text-ink-2">
                    {Object.values(row).map((v, j) => (
                      <td key={j} className="px-2.5 py-1.5 border-b border-line-soft whitespace-nowrap">{String(v)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </article>
  );
}
