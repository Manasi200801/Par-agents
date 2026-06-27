// ── /api/analyze — the bridge ────────────────────────────────────────────────
// This is the ONE place the real backend plugs in.
//
//   • PIPELINE_URL unset  → return the demo stub (build/offline mode).
//   • PIPELINE_URL set    → proxy to the real Python pipeline (run_pipeline),
//                           which returns the identical ReconcilerOutput JSON.
//
// So flipping the live demo to real Alpine data is a single env var — no UI
// change, because both paths emit the same shape (compass/contracts.py).

import { buildStubOutput } from "@/lib/stub";
import type { DecisionContext } from "@/lib/types";

// The real Opus reconciler can take 8–20s; allow headroom past the default.
export const maxDuration = 30;
export const runtime = "nodejs";

export async function POST(request: Request) {
  const ctx = (await request.json()) as DecisionContext;

  const pipelineUrl = process.env.PIPELINE_URL;
  if (pipelineUrl) {
    try {
      const res = await fetch(`${pipelineUrl.replace(/\/$/, "")}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ctx),
        // The real Opus reconciler takes 8–20s; give it room.
        signal: AbortSignal.timeout(30_000),
      });
      if (res.ok) return Response.json({ ...(await res.json()), _source: "pipeline" });
      console.error(`[analyze] pipeline ${res.status}, falling back to stub`);
    } catch (err) {
      console.error("[analyze] pipeline unreachable, falling back to stub:", err);
    }
  }

  // Small delay so the loading state is visible even with the instant stub.
  await new Promise((r) => setTimeout(r, 1100));
  return Response.json(buildStubOutput(ctx));
}
