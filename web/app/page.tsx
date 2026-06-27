"use client";

import { useMemo, useState } from "react";
import {
  PRODUCTS,
  CHANNELS,
  CHANNEL_LABELS,
  DEMO_DEFAULT,
  productById,
  orgById,
  orgsForProduct,
  machineFor,
} from "@/lib/catalog";
import type { DecisionContext, ReconcilerOutput } from "@/lib/types";
import { analyzeDecision, commitDecision } from "@/lib/pipeline";
import { AppHeader } from "@/components/AppHeader";
import { AgentCard } from "@/components/AgentCard";
import { ReconcilerPanel } from "@/components/ReconcilerPanel";
import { CompassMark, Spinner, Check, ArrowUp, ArrowDown } from "@/components/icons";

type Phase = "idle" | "analyzing" | "ready";

const _demoOrgs = orgsForProduct(DEMO_DEFAULT.product_id);
const defaultOrg =
  (_demoOrgs.find((o) => o.sales_org_id === "SO04") ?? _demoOrgs[0])?.sales_org_id ?? "";

export default function LiveDecision() {
  const [productId, setProductId] = useState<string>(DEMO_DEFAULT.product_id);
  const [salesOrgId, setSalesOrgId] = useState<string>(defaultOrg);
  const [channelId, setChannelId] = useState<string>(DEMO_DEFAULT.channel_id);

  const product = productById(productId);
  const org = orgById(salesOrgId);
  const availableOrgs = useMemo(() => orgsForProduct(productId), [productId]);
  const machineValue = machineFor(productId, salesOrgId);

  // Override kept as a string so the field can be cleared and retyped freely
  // (a plain number input forces a stuck "0"). Empty means "no change yet".
  const [overrideStr, setOverrideStr] = useState<string>(String(machineValue));
  const override = overrideStr === "" ? machineValue : Number(overrideStr);

  const [reason, setReason] = useState<string>("");
  const [planner, setPlanner] = useState<string>("planner_anna");

  const [phase, setPhase] = useState<Phase>("idle");
  const [output, setOutput] = useState<ReconcilerOutput | null>(null);
  const [ctx, setCtx] = useState<DecisionContext | null>(null);
  const [finalStr, setFinalStr] = useState<string>("");
  const [committing, setCommitting] = useState(false);
  const [decisionId, setDecisionId] = useState<string | null>(null);

  function reset() {
    setPhase("idle");
    setOutput(null);
    setCtx(null);
    setDecisionId(null);
  }

  function onProduct(id: string) {
    setProductId(id);
    const orgs = orgsForProduct(id);
    const nextOrg = orgs.some((o) => o.sales_org_id === salesOrgId) ? salesOrgId : orgs[0]?.sales_org_id ?? "";
    setSalesOrgId(nextOrg);
    setOverrideStr(String(machineFor(id, nextOrg)));
    reset();
  }

  function onOrg(id: string) {
    setSalesOrgId(id);
    setOverrideStr(String(machineFor(productId, id)));
    reset();
  }

  const pct = useMemo(
    () => ((override - machineValue) / Math.max(machineValue, 1)) * 100,
    [override, machineValue]
  );
  const changed = Math.abs(pct) > 0.5;

  async function runAnalysis() {
    if (!reason.trim()) return;
    const nextCtx: DecisionContext = {
      product_id: productId,
      sales_org_id: salesOrgId,
      channel_id: channelId,
      cutoff_date: new Date().toISOString().slice(0, 10),
      machine_value: machineValue,
      override_value: override,
      reason_text: reason,
      reason_class: null,
      business_unit: product.business_unit,
      category: product.category,
      region_group: org.region_group,
      decision_maker: planner,
    };
    setCtx(nextCtx);
    setDecisionId(null);
    setPhase("analyzing");
    try {
      const out = await analyzeDecision(nextCtx);
      setOutput(out);
      setFinalStr(String(Math.round(out.recommended_value)));
      setPhase("ready");
    } catch {
      setPhase("idle");
    }
  }

  async function commit() {
    if (!ctx || !output) return;
    setCommitting(true);
    try {
      const final = finalStr === "" ? Math.round(output.recommended_value) : Number(finalStr);
      const { decision_id } = await commitDecision(ctx, final, output);
      setDecisionId(decision_id);
    } finally {
      setCommitting(false);
    }
  }

  const canAnalyze = reason.trim().length > 0 && phase !== "analyzing";

  return (
    <main className="mx-auto max-w-[1200px] px-5 sm:px-8 pb-24">
      <AppHeader />

      <div className="mt-7 grid gap-6 lg:grid-cols-[400px_minmax(0,1fr)] items-start">
        {/* Control panel ---------------------------------------------------- */}
        <div className="panel p-5 lg:sticky lg:top-6 flex flex-col gap-5">
          <div>
            <div className="eyebrow mb-3"><span className="idx">01</span> · What you are planning</div>
            <div className="flex flex-col gap-3">
              <label className="block">
                <span className="text-[12px] text-ink-3 mb-1.5 block">Product</span>
                <select className="select" value={productId} onChange={(e) => onProduct(e.target.value)}>
                  {PRODUCTS.map((p) => (
                    <option key={p.product_id} value={p.product_id}>
                      {p.product_id} · {p.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="text-[12px] text-ink-3 mb-1.5 block">Sales region</span>
                  <select className="select" value={salesOrgId} onChange={(e) => onOrg(e.target.value)}>
                    {availableOrgs.map((o) => (
                      <option key={o.sales_org_id} value={o.sales_org_id}>{o.sales_org_id} · {o.region_group}</option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="text-[12px] text-ink-3 mb-1.5 block">Channel</span>
                  <select className="select" value={channelId} onChange={(e) => setChannelId(e.target.value)}>
                    {CHANNELS.map((c) => (
                      <option key={c} value={c}>{c} · {CHANNEL_LABELS[c]}</option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          </div>

          <div className="h-px bg-line" />

          {/* Forecast */}
          <div>
            <div className="eyebrow mb-3"><span className="idx">02</span> · Your forecast</div>
            <div className="grid grid-cols-2 gap-3">
              <div className="card p-3.5">
                <div className="text-[11px] uppercase tracking-wider text-ink-3">System forecast</div>
                <div className="mt-1 text-[26px] font-medium text-ink-2 tnum leading-none">{machineValue}</div>
                <div className="text-[11px] text-ink-4 mt-1">the automatic number</div>
              </div>
              <div className="card p-3.5" style={{ borderColor: changed ? "var(--color-line-strong)" : undefined }}>
                <div className="text-[11px] uppercase tracking-wider text-ink-3">Your number</div>
                <input
                  type="text"
                  inputMode="numeric"
                  aria-label="Your forecast number"
                  className="mt-1 w-full bg-transparent text-[26px] font-semibold text-ink tnum leading-none outline-none border-none p-0"
                  value={overrideStr}
                  onFocus={(e) => e.target.select()}
                  onChange={(e) => { setOverrideStr(e.target.value.replace(/[^0-9]/g, "")); if (phase !== "idle") reset(); }}
                />
                {changed ? (
                  <div
                    className="mt-1 inline-flex items-center gap-1 text-[11px] tnum font-medium"
                    style={{ color: pct > 0 ? "var(--color-support)" : "var(--color-caution)" }}
                  >
                    {pct > 0 ? <ArrowUp size={11} /> : <ArrowDown size={11} />}
                    {pct > 0 ? "+" : ""}{pct.toFixed(1)}% vs system
                  </div>
                ) : (
                  <div className="mt-1 text-[11px] text-ink-4">no change yet</div>
                )}
              </div>
            </div>

            <label className="block mt-3">
              <span className="text-[12px] text-ink-3 mb-1.5 block">Why are you making this change?</span>
              <textarea
                className="input"
                value={reason}
                onChange={(e) => { setReason(e.target.value); }}
                placeholder="e.g. A competitor is leaving the German market, so I expect higher demand"
              />
            </label>

            <label className="block mt-3">
              <span className="text-[12px] text-ink-3 mb-1.5 block">Your name</span>
              <input className="input" value={planner} onChange={(e) => setPlanner(e.target.value)} />
            </label>
          </div>

          <button className="btn btn-primary w-full" disabled={!canAnalyze} onClick={runAnalysis}>
            {phase === "analyzing" ? (<><Spinner /> Checking your data…</>) : (<>Check this forecast</>)}
          </button>
          {!reason.trim() && (
            <p className="text-[11.5px] text-ink-4 -mt-2 text-center">Add a reason first.</p>
          )}
        </div>

        {/* Results ---------------------------------------------------------- */}
        <div className="flex flex-col gap-6 min-w-0">
          {phase === "idle" && <EmptyState />}

          {phase === "analyzing" && <LoadingState />}

          {phase === "ready" && output && (
            <>
              <div>
                <div className="flex items-baseline justify-between mb-3 gap-3 flex-wrap">
                  <div className="eyebrow"><span className="idx">03</span> · What your data shows</div>
                  <div className="flex items-center gap-2">
                    {output._source === "stub" && (
                      <span className="chip" style={{ color: "var(--color-caution)", borderColor: "rgba(226,163,60,0.35)" }} title="The live model (P2/P3) is not connected yet. Products and forecasts are real; this evidence is an illustrative preview.">
                        Preview evidence
                      </span>
                    )}
                    <span className="text-[12px] text-ink-4 tnum">{output.signals_used.length} sources checked</span>
                  </div>
                </div>
                {output.signals_used.length > 0 ? (
                  <div className="grid gap-4 sm:grid-cols-2">
                    {output.signals_used.map((s, i) => (
                      <AgentCard key={s.agent_name + i} signal={s} index={i} />
                    ))}
                  </div>
                ) : (
                  <div className="card p-5 text-[13px] text-ink-3">No data signals for this combination yet.</div>
                )}
              </div>

              <ReconcilerPanel output={output} machineValue={machineValue} overrideValue={override} />

              {/* Step 4 — decide */}
              <section className="fade-up" style={{ animationDelay: "460ms" }}>
                <div className="eyebrow mb-3"><span className="idx">04</span> · Your decision</div>
                {decisionId ? (
                  <div className="card p-5 flex items-start gap-3">
                    <span className="mt-0.5 grid place-items-center h-6 w-6 rounded-full shrink-0" style={{ background: "rgba(76,183,130,0.15)", color: "var(--color-support)" }}>
                      <Check />
                    </span>
                    <div>
                      <div className="text-[14px] text-ink">Saved · <code className="text-ink-2">{decisionId}</code></div>
                      <p className="text-[12.5px] text-ink-3 mt-1 leading-relaxed max-w-prose">
                        This decision is saved and linked to similar products. When the real sales come in, Compass checks whether it was right and learns from it, so the next person gets better advice.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="card p-4 flex flex-col sm:flex-row sm:items-end gap-4">
                    <label className="block">
                      <span className="text-[12px] text-ink-3 mb-1.5 block">Final number you commit to</span>
                      <input
                        type="text"
                        inputMode="numeric"
                        aria-label="Final number"
                        className="input tnum text-[18px] font-medium sm:w-[160px]"
                        value={finalStr}
                        onFocus={(e) => e.target.select()}
                        onChange={(e) => setFinalStr(e.target.value.replace(/[^0-9]/g, ""))}
                      />
                    </label>
                    <div className="flex items-center gap-2 text-[12px] text-ink-4 sm:pb-2.5">
                      <button className="btn btn-ghost" onClick={() => setFinalStr(String(Math.round(output.recommended_value)))}>Use {Math.round(output.recommended_value)}</button>
                      <button className="btn btn-ghost" onClick={() => setFinalStr(String(override))}>Keep {override}</button>
                    </div>
                    <button className="btn btn-primary sm:ml-auto" onClick={commit} disabled={committing}>
                      {committing ? (<><Spinner /> Saving…</>) : (<><Check /> Commit this number</>)}
                    </button>
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </div>
    </main>
  );
}

function EmptyState() {
  return (
    <div className="panel p-10 grid place-items-center text-center min-h-[420px]">
      <div className="max-w-sm">
        <div className="mx-auto mb-4 text-ink-4 opacity-40"><CompassMark size={44} /></div>
        <h2 className="text-[16px] font-medium text-ink-2">Nothing to check yet</h2>
        <p className="mt-2 text-[13px] text-ink-3 leading-relaxed">
          Enter your forecast and the reason behind it, then check it. Compass looks at your live data from several angles and suggests a number you can trust.
        </p>
      </div>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="eyebrow mb-3"><span className="idx">03</span> · What your data shows</div>
        <div className="grid gap-4 sm:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-[168px] border border-line" style={{ animationDelay: `${i * 120}ms` }} />
          ))}
        </div>
      </div>
      <div className="skeleton h-[220px] border border-line" />
    </div>
  );
}
