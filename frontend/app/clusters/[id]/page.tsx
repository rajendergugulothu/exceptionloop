"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type Cluster, type ReadinessScore, type WorkflowSpec } from "@/lib/api";

const DIM_LABELS: Record<string, string> = {
  frequency_score: "Frequency",
  consistency_score: "Resolution Consistency",
  data_completeness_score: "Data Completeness",
  risk_score: "Risk",
  reversibility_score: "Reversibility",
  policy_clarity_score: "Policy Clarity",
  integration_stability_score: "Integration Stability",
  evaluation_feasibility_score: "Evaluation Feasibility",
};

function ScoreBar({ value }: { value: number | null }) {
  if (value === null) return <span style={{ color: "var(--text-2)" }}>—</span>;
  const pct = Math.round(value * 100);
  const color = value >= 0.8 ? "var(--teal)" : value >= 0.6 ? "var(--amber)" : "var(--red)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 6, background: "var(--surface-2)", borderRadius: 3, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 12, color, width: 32, textAlign: "right" }}>{pct}%</span>
    </div>
  );
}

export default function ClusterDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [cluster, setCluster] = useState<Cluster | null>(null);
  const [readiness, setReadiness] = useState<ReadinessScore | null>(null);
  const [spec, setSpec] = useState<WorkflowSpec | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [purityInput, setPurityInput] = useState({ score: "0.85", reviewer: "", notes: "" });

  useEffect(() => {
    Promise.all([
      api.clusters.get(id),
      api.clusters.getReadiness(id).catch(() => null),
      api.clusters.getSpec(id).catch(() => null),
    ])
      .then(([c, r, s]) => { setCluster(c); setReadiness(r); setSpec(s); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  async function run<T>(label: string, fn: () => Promise<T>, onDone: (r: T) => void) {
    setWorking(label);
    setError(null);
    try {
      onDone(await fn());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : label + " failed");
    } finally {
      setWorking(null);
    }
  }

  if (loading) return <div className="loading-state" style={{ padding: "80px" }}>Loading cluster…</div>;
  if (!cluster) return <div className="error-state" style={{ margin: 24 }}>{error}</div>;

  return (
    <>
      <nav className="nav">
        <Link href={`/workspace/${cluster.workspace_id}/clusters`} className="nav-link">← Pipeline</Link>
        <span className="nav-brand" style={{ fontSize: 13 }}>{cluster.label}</span>
        <span style={{ flex: 1 }} />
        <span className="badge badge-neutral">{cluster.status.replace(/_/g, " ")}</span>
      </nav>

      <div className="page-container" style={{ maxWidth: 800 }}>
        {error && <div className="error-state" style={{ marginBottom: 16 }}>{error}</div>}

        {/* Cluster overview */}
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="grid-3">
            <div className="stat">
              <div className="stat-value">{cluster.case_count}</div>
              <div className="stat-label">Cases</div>
            </div>
            <div className="stat">
              <div className="stat-value">{cluster.purity_score !== null ? `${Math.round(cluster.purity_score * 100)}%` : "—"}</div>
              <div className="stat-label">Purity</div>
            </div>
            <div className="stat">
              <div className="stat-value">{cluster.resolution_consistency !== null ? `${Math.round(cluster.resolution_consistency * 100)}%` : "—"}</div>
              <div className="stat-label">Consistency</div>
            </div>
          </div>
        </div>

        {/* Purity review */}
        {cluster.status === "purity_review" && (
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="label">Purity Review</div>
            <p style={{ fontSize: 13, color: "var(--text-2)", marginTop: 6, marginBottom: 14 }}>
              Assess whether the cases in this cluster are genuinely the same exception type. &gt;= 80% required to advance.
            </p>
            <div style={{ display: "flex", gap: 10, marginBottom: 12 }}>
              <input className="input" style={{ width: 100 }} placeholder="Score 0–1" value={purityInput.score}
                onChange={(e) => setPurityInput((p) => ({ ...p, score: e.target.value }))} />
              <input className="input" placeholder="Reviewer email" value={purityInput.reviewer}
                onChange={(e) => setPurityInput((p) => ({ ...p, reviewer: e.target.value }))} />
            </div>
            <input className="input" placeholder="Notes (optional)" value={purityInput.notes}
              onChange={(e) => setPurityInput((p) => ({ ...p, notes: e.target.value }))}
              style={{ marginBottom: 12 }} />
            <button
              className="btn btn-primary"
              disabled={!!working}
              onClick={() => run("Submitting purity review", () =>
                api.clusters.purityReview(id, purityInput.reviewer, Number(purityInput.score), purityInput.notes),
                (c) => setCluster(c)
              )}
            >
              {working === "Submitting purity review" ? "Submitting…" : "Submit Purity Assessment"}
            </button>
          </div>
        )}

        {/* Readiness scoring */}
        {(cluster.status === "ready_for_scoring" || readiness) && (
          <div className="card" style={{ marginBottom: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <div className="label">Automation Readiness (8 Dimensions)</div>
              {!readiness && (
                <button
                  className="btn btn-secondary"
                  disabled={!!working}
                  onClick={() => run("Scoring readiness", () => api.clusters.scoreReadiness(id), setReadiness)}
                >
                  {working === "Scoring readiness" ? "Scoring…" : "Score Readiness"}
                </button>
              )}
              {readiness && (
                <span style={{ fontSize: 18, fontWeight: 700, color: (readiness.total_score ?? 0) >= 0.7 ? "var(--teal)" : "var(--amber)" }}>
                  {readiness.total_score !== null ? `${Math.round(readiness.total_score * 100)}%` : "—"}
                </span>
              )}
            </div>

            {readiness && (
              <>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {Object.entries(DIM_LABELS).map(([key, label]) => (
                    <div key={key}>
                      <div style={{ fontSize: 12, color: "var(--text-2)", marginBottom: 4 }}>{label}</div>
                      <ScoreBar value={(readiness as Record<string, number | null>)[key] as number | null} />
                    </div>
                  ))}
                </div>
                {readiness.blockers.length > 0 && (
                  <div style={{ marginTop: 14, padding: 12, background: "var(--red-dim)", borderRadius: 6, border: "1px solid rgba(255,69,96,0.25)" }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "var(--red)", marginBottom: 6 }}>Blockers</div>
                    {readiness.blockers.map((b, i) => (
                      <div key={i} style={{ fontSize: 12, color: "var(--text-2)", marginBottom: 2 }}>• {b}</div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Workflow spec */}
        {(cluster.status === "scored" || cluster.status === "workflow_generated" || spec) && (
          <div className="card" style={{ marginBottom: 20 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
              <div className="label">Workflow Specification</div>
              {!spec && (
                <button
                  className="btn btn-secondary"
                  disabled={!!working}
                  onClick={() => run("Generating spec", () => api.clusters.generateSpec(id), setSpec)}
                >
                  {working === "Generating spec" ? "Generating…" : "Generate Spec"}
                </button>
              )}
            </div>

            {spec && (
              <>
                <div style={{ marginBottom: 12 }}>
                  <div className="label">Trigger</div>
                  <p style={{ fontSize: 13, marginTop: 4 }}>{spec.trigger}</p>
                </div>
                <div style={{ marginBottom: 12 }}>
                  <div className="label">Required Inputs</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 4 }}>
                    {spec.required_inputs.map((inp) => (
                      <span key={inp} className="badge badge-neutral">{inp}</span>
                    ))}
                  </div>
                </div>
                <div style={{ marginBottom: 12 }}>
                  <div className="label">Steps</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 6 }}>
                    {spec.steps.map((step, i) => (
                      <div key={i} style={{ background: "var(--surface-2)", borderRadius: 6, padding: "10px 12px" }}>
                        <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 4 }}>Step {i + 1}</div>
                        <div style={{ fontSize: 13 }}>{step.description}</div>
                        {step.source_case_ids?.length > 0 && (
                          <div style={{ fontSize: 11, color: "var(--text-2)", marginTop: 4 }}>
                            Based on {step.source_case_ids.length} resolved case(s)
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Pipeline advance */}
                {spec.pipeline_stage !== "shipped" && (
                  <div style={{ display: "flex", gap: 8, marginTop: 16, flexWrap: "wrap" }}>
                    {spec.pipeline_stage === "candidates" && (
                      <button
                        className="btn btn-primary"
                        disabled={!!working}
                        onClick={() => run("Approving", () =>
                          api.clusters.advancePipeline(spec.id, "ai_pm", "approved"),
                          (s) => setSpec(s)
                        )}
                      >
                        {working === "Approving" ? "…" : "Approve for Pipeline"}
                      </button>
                    )}
                    {spec.pipeline_stage === "approved" && (
                      <button
                        className="btn btn-secondary"
                        disabled={!!working}
                        onClick={() => run("Advancing", () =>
                          api.clusters.advancePipeline(spec.id, "engineering", "in_development"),
                          (s) => setSpec(s)
                        )}
                      >
                        Mark In Development
                      </button>
                    )}
                    {spec.pipeline_stage === "in_development" && (
                      <button
                        className="btn btn-primary"
                        style={{ background: "var(--teal)" }}
                        disabled={!!working}
                        onClick={() => run("Shipping", () =>
                          api.clusters.advancePipeline(spec.id, "engineering", "shipped"),
                          (s) => setSpec(s)
                        )}
                      >
                        Mark Shipped
                      </button>
                    )}
                  </div>
                )}

                {spec.pipeline_stage === "shipped" && (
                  <div style={{ marginTop: 12, color: "var(--teal)", fontWeight: 600 }}>
                    ✓ Shipped — this exception class is now automated
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </>
  );
}
