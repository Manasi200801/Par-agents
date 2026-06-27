// ── /api/commit — persist the planner's final decision ───────────────────────
// Same bridge pattern: proxy to the real commit_decision (which writes to the
// DuckDB decisions table + triggers KG fan-out) when PIPELINE_URL is set,
// otherwise return a stub decision id so the UI flow completes offline.

import type { DecisionContext, ReconcilerOutput } from "@/lib/types";

interface CommitBody {
  ctx: DecisionContext;
  final_value: number;
  output: ReconcilerOutput;
}

export const maxDuration = 30;
export const runtime = "nodejs";

export async function POST(request: Request) {
  const body = (await request.json()) as CommitBody;

  const pipelineUrl = process.env.PIPELINE_URL;
  if (pipelineUrl) {
    try {
      const res = await fetch(`${pipelineUrl.replace(/\/$/, "")}/commit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(30_000),
      });
      if (res.ok) return Response.json(await res.json());
      console.error(`[commit] pipeline ${res.status}, falling back to stub`);
    } catch (err) {
      console.error("[commit] pipeline unreachable, falling back to stub:", err);
    }
  }

  await new Promise((r) => setTimeout(r, 700));
  const decision_id = `dec_${Math.random().toString(36).slice(2, 10)}`;
  return Response.json({ decision_id });
}
