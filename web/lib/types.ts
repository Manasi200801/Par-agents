// TypeScript port of compass/contracts.py (Ash-code branch).
// SHARED CONTRACT — keep field names in lockstep with the Python dataclasses.
// When the real backend lands, the JSON returned by run_pipeline must match these.

export type Direction = "supports_override" | "contradicts_override" | "neutral";
export type Confidence = "low" | "medium" | "high";

/** Passed INTO every agent and the reconciler. */
export interface DecisionContext {
  product_id: string;
  sales_org_id: string;
  channel_id: string;
  cutoff_date: string; // ISO date
  machine_value: number; // stat_forecast qty
  override_value: number; // what the planner is proposing
  reason_text: string;
  reason_class: string | null; // filled after the Haiku classifier runs
  business_unit: string;
  category: string;
  region_group: string;
  decision_maker: string;
}

/** What every agent returns. Empty list = the agent stays silent. */
export interface Signal {
  agent_name: string;
  claim: string; // one plain-English sentence
  direction: Direction;
  magnitude: number; // 0.0 – 1.0, how strong the signal is
  confidence: number; // 0.0 – 1.0, how sure the agent is
  table: string; // which source table was read
  evidence_rows: Record<string, unknown>[]; // the actual rows
}

export interface PastEvent {
  reason_text: string;
  reason_class: string;
  realized_impact_pct: number;
  fva: number;
  cutoff_date: string;
}

/** What the Memory / Critic agent returns. */
export interface MemoryContext {
  planner_fva_history: {
    avg_fva?: number;
    n_decisions?: number;
    pct_helpful?: number;
  };
  reason_type_history: {
    avg_fva?: number;
    avg_override_pct?: number;
    avg_realized_pct?: number;
    n?: number;
  };
  similar_past_events: PastEvent[];
  calibrated_suggestion: number | null;
  confidence_level: Confidence;
}

/** What the Reconciler returns to the frontend. */
export interface ReconcilerOutput {
  recommended_value: number;
  confidence_level: Confidence;
  rationale: string; // plain English, 2-4 sentences
  signals_used: Signal[];
  memory_context: MemoryContext;
  // Set by the API route so the UI can honestly mark stubbed vs live evidence.
  _source?: "stub" | "pipeline";
}

/** Written to the decisions table after the planner commits. */
export interface DecisionRecord {
  decision_id: string;
  item_id: string; // `${product_id}__${sales_org_id}__${channel_id}`
  machine_value: number;
  override_value: number;
  reconciler_value: number;
  final_value: number;
  reason_text: string;
  reason_class: string;
  decision_maker: string;
}
