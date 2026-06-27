import { AppHeader } from "@/components/AppHeader";
import { ReplayChart } from "@/components/ReplayChart";
import { HEADLINE, REPLAY } from "@/lib/replay-data";

const pctImprovement = Math.round(
  ((HEADLINE.mae_machine - HEADLINE.mae_planner) / HEADLINE.mae_machine) * 100
);

function Kpi({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub: string;
  accent?: string;
}) {
  return (
    <div className="card p-4">
      <div className="text-[11px] uppercase tracking-wider text-ink-3">{label}</div>
      <div className="mt-1.5 text-[30px] font-semibold tnum leading-none" style={{ color: accent ?? "var(--color-ink)" }}>
        {value}
      </div>
      <div className="mt-1.5 text-[12px] text-ink-3 leading-snug">{sub}</div>
    </div>
  );
}

export default function ReplayDashboard() {
  return (
    <main className="mx-auto max-w-[1200px] px-5 sm:px-8 pb-24">
      <AppHeader />

      <div className="mt-7 flex flex-col gap-6">
        <div>
          <h1 className="text-[22px] font-semibold tracking-[-0.01em] text-ink">Track record</h1>
          <p className="mt-1 text-[13.5px] text-ink-3 max-w-2xl leading-relaxed">
            {HEADLINE.cutoffs} real planning cycles, scored against what actually sold.
            This is how human changes have performed against the automatic forecast, and what Compass would add.
          </p>
        </div>

        {/* KPIs ------------------------------------------------------------- */}
        <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
          <Kpi
            label="Planners change the number"
            value={`${Math.round(HEADLINE.exact_override_share * 100)}%`}
            sub="of the time, almost every cycle"
          />
          <Kpi
            label="Changes that helped"
            value={`${Math.round(HEADLINE.pct_helped_meaningful * 100)}%`}
            sub="of meaningful changes improved the forecast"
            accent="var(--color-support)"
          />
          <Kpi
            label="Error vs automatic"
            value={`${pctImprovement}% lower`}
            sub={`planner error ${Math.round(HEADLINE.mae_planner)} vs system ${Math.round(HEADLINE.mae_machine)}`}
            accent="var(--color-support)"
          />
          <Kpi
            label="Typical change size"
            value={`${Math.round(HEADLINE.median_abs_meaningful_override_pct * 100)}%`}
            sub="median adjustment away from the system number"
          />
        </div>

        {/* Chart ------------------------------------------------------------ */}
        <section className="panel p-5">
          <div className="flex items-baseline justify-between gap-3 flex-wrap mb-1">
            <h2 className="text-[15px] font-medium text-ink">Forecast error over time</h2>
            <span className="text-[12px] text-ink-4">average error per cycle · lower is better</span>
          </div>
          <ReplayChart data={REPLAY} />
        </section>

        {/* Honest note ------------------------------------------------------ */}
        <div className="card p-4 text-[12.5px] text-ink-3 leading-relaxed max-w-3xl">
          <span className="text-ink-2 font-medium">How to read this.</span> Lower error is better. The system
          line is the automatic forecast, the planner line is what people committed, and the Compass line is a
          projection that keeps the changes that helped and eases back the ones that hurt. Compass does not
          replace the planner: it points out which changes to trust and which to rethink, which is what it
          coaches in the live view.
        </div>
      </div>
    </main>
  );
}
