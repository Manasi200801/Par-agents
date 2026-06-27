import type { ReconcilerOutput, Confidence } from "@/lib/types";
import { ArrowUp, ArrowDown } from "./icons";

const CONF: Record<Confidence, { label: string; color: string; fill: number }> = {
  high: { label: "High confidence", color: "var(--color-support)", fill: 3 },
  medium: { label: "Medium confidence", color: "var(--color-caution)", fill: 2 },
  low: { label: "Low confidence", color: "var(--color-danger)", fill: 1 },
};

function ConfidenceMeter({ level }: { level: Confidence }) {
  const c = CONF[level];
  return (
    <div className="inline-flex items-center gap-2.5">
      <span className="seg">
        {[0, 1, 2].map((i) => (
          <i key={i} style={i < c.fill ? { background: c.color, width: 22 } : { width: 22 }} />
        ))}
      </span>
      <span className="text-[12.5px] font-medium" style={{ color: c.color }}>{c.label}</span>
    </div>
  );
}

function Figure({ label, value, accent, delta }: { label: string; value: number; accent?: boolean; delta?: number }) {
  return (
    <div className="flex-1 min-w-0">
      <div className="text-[11px] uppercase tracking-wider text-ink-3">{label}</div>
      <div className={`mt-1 tnum leading-none ${accent ? "text-[34px] font-semibold text-ink" : "text-[28px] font-medium text-ink-2"}`}>
        {Math.round(value)}
      </div>
      {delta !== undefined && delta !== 0 && (
        <div
          className="mt-1.5 inline-flex items-center gap-1 text-[12px] tnum font-medium"
          style={{ color: delta > 0 ? "var(--color-support)" : "var(--color-caution)" }}
        >
          {delta > 0 ? <ArrowUp /> : <ArrowDown />}
          {delta > 0 ? "+" : ""}{Math.round(delta)} vs system
        </div>
      )}
    </div>
  );
}

export function ReconcilerPanel({
  output,
  machineValue,
  overrideValue,
}: {
  output: ReconcilerOutput;
  machineValue: number;
  overrideValue: number;
}) {
  const mem = output.memory_context;
  const hasMemory = mem.similar_past_events.length > 0 || (mem.planner_fva_history.n_decisions ?? 0) > 0;

  return (
    <section className="fade-up panel p-5" style={{ animationDelay: "380ms" }}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2.5">
          <span className="h-2 w-2 rounded-full" style={{ background: "var(--color-brand-2)", boxShadow: "0 0 10px var(--color-brand-2)" }} />
          <h2 className="text-[15px] font-medium text-ink">Compass recommendation</h2>
        </div>
        <ConfidenceMeter level={output.confidence_level} />
      </div>

      <div className="mt-5 flex items-end gap-4">
        <Figure label="System forecast" value={machineValue} />
        <span className="text-ink-4 pb-2">→</span>
        <Figure label="Your number" value={overrideValue} />
        <span className="text-ink-4 pb-2">→</span>
        <Figure label="Compass suggests" value={output.recommended_value} accent delta={output.recommended_value - machineValue} />
      </div>

      <p className="mt-5 text-[13.5px] leading-relaxed text-ink-2 border-l-2 pl-3.5" style={{ borderColor: "var(--color-brand)" }}>
        {output.rationale}
      </p>

      {hasMemory && (
        <details className="mt-4 group">
          <summary className="cursor-pointer list-none text-[12.5px] text-ink-3 hover:text-ink-2 transition-colors select-none">
            <span className="inline-block transition-transform group-open:rotate-90">›</span>{" "}
            Track record
          </summary>

          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {(mem.planner_fva_history.n_decisions ?? 0) > 0 && (
              <div className="card p-3.5">
                <div className="text-[11px] uppercase tracking-wider text-ink-3">Your past changes</div>
                <div className="mt-1.5 text-[13px] text-ink-2 tnum">
                  {Math.round((mem.planner_fva_history.pct_helpful ?? 0) * 100)}% made the forecast better
                  <span className="text-ink-4"> · {mem.planner_fva_history.n_decisions} so far</span>
                </div>
                <div className="mt-1 text-[12px] text-ink-4 tnum">
                  on average {(mem.planner_fva_history.avg_fva ?? 0) > 0 ? "improved it by " : "off by "}{Math.abs(Math.round(mem.planner_fva_history.avg_fva ?? 0))} units
                </div>
              </div>
            )}
            {(mem.reason_type_history.n ?? 0) > 0 && (
              <div className="card p-3.5">
                <div className="text-[11px] uppercase tracking-wider text-ink-3">This kind of reason</div>
                <div className="mt-1.5 text-[13px] text-ink-2 tnum">
                  people aimed for +{Math.round(mem.reason_type_history.avg_override_pct ?? 0)}%, reality was +{Math.round(mem.reason_type_history.avg_realized_pct ?? 0)}%
                </div>
                <div className="mt-1 text-[12px] text-ink-4">people usually push this a little too far</div>
              </div>
            )}
          </div>

          {mem.similar_past_events.length > 0 && (
            <div className="mt-3">
              <div className="text-[11px] uppercase tracking-wider text-ink-3 mb-2">Similar past cases</div>
              <ul className="flex flex-col gap-1.5">
                {mem.similar_past_events.slice(0, 3).map((e, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-[12.5px]">
                    <span
                      className="mt-1.5 h-1.5 w-1.5 rounded-full shrink-0"
                      style={{ background: e.fva > 0 ? "var(--color-support)" : "var(--color-caution)" }}
                    />
                    <span className="text-ink-2 leading-snug">
                      <span className="italic text-ink-3">&ldquo;{e.reason_text}&rdquo;</span>
                      <span className="tnum text-ink-4">. Reality came in at +{e.realized_impact_pct}%.</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </details>
      )}
    </section>
  );
}
