// ── The integration seam ─────────────────────────────────────────────────────
// The UI ONLY talks to these two functions. They POST to our own API routes.
// Today those routes return the stub; the day the real Python pipeline is
// reachable, only the route changes (set PIPELINE_URL) — the UI never knows.

import type { DecisionContext, ReconcilerOutput } from "./types";

export async function analyzeDecision(
  ctx: DecisionContext
): Promise<ReconcilerOutput> {
  const res = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(ctx),
  });
  if (!res.ok) throw new Error(`analyze failed: ${res.status}`);
  return res.json();
}

export async function commitDecision(
  ctx: DecisionContext,
  finalValue: number,
  output: ReconcilerOutput
): Promise<{ decision_id: string }> {
  const res = await fetch("/api/commit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ctx, final_value: finalValue, output }),
  });
  if (!res.ok) throw new Error(`commit failed: ${res.status}`);
  return res.json();
}
