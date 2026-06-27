// ── Demo pipeline stub ───────────────────────────────────────────────────────
// Server-side stand-in for the real compass.run_pipeline (Ash-code/P3).
// Returns the EXACT ReconcilerOutput shape so the UI is identical whether it's
// driven by this stub or the real Python pipeline. Swap point lives in the
// /api/analyze route handler — see app/api/analyze/route.ts.
//
// This is scaffolding for BUILDING the UI offline. For the live demo, the route
// proxies to the real pipeline (PIPELINE_URL) so judges see genuine numbers.

import type {
  DecisionContext,
  MemoryContext,
  ReconcilerOutput,
  Signal,
  Confidence,
} from "./types";

/** Mirrors compass/classifier.py keyword fallback. */
export function classifyReason(reason: string): string {
  const r = reason.toLowerCase();
  const map: [string, string][] = [
    ["promot", "promotion"],
    ["campaign", "promotion"],
    ["black friday", "promotion"],
    ["competitor", "competitor_exit"],
    ["rival", "competitor_exit"],
    ["exit", "competitor_exit"],
    ["overstock", "channel_overstock"],
    ["stock", "channel_overstock"],
    ["tariff", "macro_signal"],
    ["price", "price_change"],
    ["supply", "supply_constraint"],
    ["shortage", "supply_constraint"],
    ["delay", "supply_constraint"],
  ];
  for (const [kw, cls] of map) if (r.includes(kw)) return cls;
  return "other";
}

const round = (n: number) => Math.round(n);

// Calibration grounded in the real Alpine stat: upward overrides are right ~71%
// of the time, downward only ~34%. So we trust upward moves more than downward.
function calibrate(machine: number, override: number): number {
  const gap = override - machine;
  if (gap === 0) return machine;
  const trust = gap > 0 ? 0.7 : 0.34;
  return round(machine + gap * trust);
}

function confidenceFrom(signals: Signal[], hasMemory: boolean): Confidence {
  const support = signals.filter((s) => s.direction === "supports_override").length;
  const against = signals.filter((s) => s.direction === "contradicts_override").length;
  const score = support - against + (hasMemory ? 1 : 0);
  if (score >= 2) return "high";
  if (score >= 1) return "medium";
  return "low";
}

// ── The canonical demo: CP-0271 × SO04 × CH01, competitor-exit upward override ─
function demoSignals(ctx: DecisionContext): Signal[] {
  return [
    {
      agent_name: "Demand",
      claim:
        "The order book has 3 confirmed orders totalling 182 units for the next cycle. That is 22% more than the same time last year.",
      direction: "supports_override",
      magnitude: 0.62,
      confidence: 0.74,
      table: "future_order_book",
      evidence_rows: [
        { customer: "Kaufmann GmbH", qty: 84, status: "confirmed", week: "2026-W28" },
        { customer: "Brandt AG", qty: 60, status: "confirmed", week: "2026-W29" },
        { customer: "Voss KG", qty: 38, status: "tentative", week: "2026-W30" },
      ],
    },
    {
      agent_name: "Supply",
      claim:
        "There is only about 2 weeks of stock left, and this supplier delivers on time only 71% of the time. A big increase risks running out.",
      direction: "contradicts_override",
      magnitude: 0.55,
      confidence: 0.68,
      table: "stock_on_hand",
      evidence_rows: [
        { metric: "stock on hand", value: 918, unit: "units" },
        { metric: "weeks of cover", value: 2.1 },
        { metric: "on-time delivery", value: "71%" },
      ],
    },
    {
      agent_name: "Finance",
      claim:
        "Margin is healthy at 34%, so a higher plan adds profit if the demand actually shows up.",
      direction: "neutral",
      magnitude: 0.4,
      confidence: 0.6,
      table: "cost_breakdown",
      evidence_rows: [
        { unit_price: 11.4, unit_cost: 7.52, margin_pct: 34 },
      ],
    },
    {
      agent_name: "Commercial",
      claim:
        "No competing promotions this cycle, and a rival leaving the German bearings market fits your reason for raising the number.",
      direction: "supports_override",
      magnitude: 0.5,
      confidence: 0.55,
      table: "price_changes",
      evidence_rows: [
        { competitor: "Bauer Tools", segment: "bearings", region: "DACH", note: "leaving the market" },
      ],
    },
  ];
}

function demoMemory(): MemoryContext {
  return {
    planner_fva_history: { avg_fva: 28.4, n_decisions: 6, pct_helpful: 0.67 },
    reason_type_history: {
      avg_fva: 47.3,
      avg_override_pct: 18.5,
      avg_realized_pct: 13.1,
      n: 3,
    },
    similar_past_events: [
      { reason_text: "Competitor Bauer Tools rumoured to be exiting DACH market for bearings", reason_class: "competitor_exit", realized_impact_pct: 17, fva: 61, cutoff_date: "2025-03-01" },
      { reason_text: "Heard at trade show that rival exiting Nordic fasteners segment", reason_class: "competitor_exit", realized_impact_pct: 12, fva: 38, cutoff_date: "2025-04-01" },
      { reason_text: "Key competitor pulling out of composites in France", reason_class: "competitor_exit", realized_impact_pct: 17, fva: 30, cutoff_date: "2025-05-01" },
    ],
    calibrated_suggestion: 494,
    confidence_level: "high",
  };
}

// ── Generic grounded path for any other product/reason ───────────────────────
function genericSignals(ctx: DecisionContext, cls: string): Signal[] {
  const up = ctx.override_value >= ctx.machine_value;
  const dir = up ? "supports_override" : "contradicts_override";
  return [
    {
      agent_name: "Demand",
      claim: up
        ? `Order book for ${ctx.product_id} is trending above the statistical baseline in ${ctx.region_group}.`
        : `Order book for ${ctx.product_id} shows softening confirmed demand in ${ctx.region_group}.`,
      direction: dir,
      magnitude: 0.5,
      confidence: 0.6,
      table: "future_order_book",
      evidence_rows: [{ product_id: ctx.product_id, region: ctx.region_group, trend: up ? "up" : "down" }],
    },
    {
      agent_name: "Supply / Ops",
      claim: `Stock and supplier reliability look adequate for ${ctx.product_id} at the proposed level.`,
      direction: "neutral",
      magnitude: 0.35,
      confidence: 0.55,
      table: "stock_on_hand",
      evidence_rows: [{ product_id: ctx.product_id, weeks_cover: 4.2 }],
    },
    {
      agent_name: "Memory / Critic",
      claim:
        cls === "channel_overstock"
          ? "Downward overstock overrides at Alpine have historically helped only ~34% of the time."
          : `Past "${cls}" overrides in this category realised less than the planner proposed on average.`,
      direction: "contradicts_override",
      magnitude: 0.45,
      confidence: 0.6,
      table: "decisions",
      evidence_rows: [{ reason_class: cls, avg_realized_pct: up ? 9 : -6 }],
    },
  ];
}

function genericMemory(cls: string): MemoryContext {
  return {
    planner_fva_history: { avg_fva: 4.1, n_decisions: 3, pct_helpful: 0.5 },
    reason_type_history: { avg_fva: -8.0, avg_override_pct: 14, avg_realized_pct: 7, n: 2 },
    similar_past_events: [],
    calibrated_suggestion: null,
    confidence_level: "low",
  };
}

const isDemo = (ctx: DecisionContext) =>
  ctx.product_id === "CP-0271" &&
  ctx.sales_org_id === "SO04" &&
  ctx.override_value > ctx.machine_value;

export function buildStubOutput(ctx: DecisionContext): ReconcilerOutput {
  const cls = ctx.reason_class ?? classifyReason(ctx.reason_text);

  if (isDemo(ctx)) {
    const rec = calibrate(ctx.machine_value, ctx.override_value);
    const upPct = Math.round(((ctx.override_value - ctx.machine_value) / ctx.machine_value) * 100);
    return {
      recommended_value: rec,
      confidence_level: "medium",
      rationale: `Demand and market signals point to a higher number, and a rival leaving the German market fits your reason. But in similar past cases this kind of move landed around +13%, not the +${upPct}% you proposed, and stock cover is tight. Compass suggests ${rec}. It keeps most of the upside while staying close to what these situations have delivered before.`,
      signals_used: demoSignals(ctx),
      memory_context: demoMemory(),
      _source: "stub",
    };
  }

  const signals = genericSignals(ctx, cls);
  const memory = genericMemory(cls);
  return {
    recommended_value: calibrate(ctx.machine_value, ctx.override_value),
    confidence_level: confidenceFrom(signals, memory.similar_past_events.length > 0),
    rationale:
      ctx.override_value === ctx.machine_value
        ? "You have not changed the number yet, so the suggestion matches the system forecast. Enter a different number and a reason to see what the data says."
        : `This looks like a "${cls.replace(/_/g, " ")}" change. In the past, ${
            ctx.override_value > ctx.machine_value ? "raising" : "lowering"
          } the number for this kind of reason has usually moved it less than people expect, so Compass keeps your number partway back toward the system forecast of ${ctx.machine_value}.`,
    signals_used: signals,
    memory_context: memory,
    _source: "stub",
  };
}
