"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type Cluster, type PipelineView } from "@/lib/api";

const STAGE_LABELS: Record<string, string> = {
  candidates: "Candidates",
  approved: "Approved",
  in_development: "In Development",
  shipped: "Shipped",
};

const STATUS_COLOR: Record<string, string> = {
  forming: "var(--text-2)",
  purity_review: "var(--amber)",
  ready_for_scoring: "var(--accent)",
  scored: "var(--accent)",
  workflow_generated: "var(--teal)",
  approved: "var(--teal)",
  in_development: "var(--orange)",
  shipped: "var(--teal)",
};

function ClusterCard({ cluster, workspaceId }: { cluster: Cluster; workspaceId: string }) {
  return (
    <div className="card" style={{ marginBottom: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>{cluster.label}</div>
        <span style={{ fontSize: 11, color: STATUS_COLOR[cluster.status] ?? "var(--text-2)" }}>
          {cluster.status.replace(/_/g, " ")}
        </span>
      </div>
      <div style={{ fontSize: 12, color: "var(--text-2)", marginBottom: 10 }}>
        {cluster.case_count} cases
        {cluster.purity_score !== null && ` · ${Math.round(cluster.purity_score * 100)}% purity`}
        {cluster.resolution_consistency !== null && ` · ${Math.round(cluster.resolution_consistency * 100)}% consistency`}
      </div>
      <Link href={`/clusters/${cluster.id}`}>
        <button className="btn btn-secondary" style={{ fontSize: 12 }}>View Cluster →</button>
      </Link>
    </div>
  );
}

export default function ClustersPage() {
  const { id } = useParams<{ id: string }>();
  const [pipeline, setPipeline] = useState<PipelineView | null>(null);
  const [loading, setLoading] = useState(true);
  const [clustering, setClustering] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.clusters.pipeline(id)
      .then(setPipeline)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  async function runClustering() {
    setClustering(true);
    setError(null);
    try {
      await api.clusters.run(id);
      const p = await api.clusters.pipeline(id);
      setPipeline(p);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Clustering failed");
    } finally {
      setClustering(false);
    }
  }

  if (loading) return <div className="loading-state" style={{ padding: "80px" }}>Loading pipeline…</div>;

  const stages: Array<{ key: keyof PipelineView; label: string }> = [
    { key: "candidates", label: "Candidates" },
    { key: "approved", label: "Approved" },
    { key: "in_development", label: "In Development" },
    { key: "shipped", label: "Shipped" },
  ];

  return (
    <>
      <nav className="nav">
        <Link href={`/workspace/${id}`} className="nav-link">← Workspace</Link>
        <span className="nav-brand" style={{ fontSize: 14 }}>Exception Pipeline</span>
        <span style={{ flex: 1 }} />
        {pipeline && (
          <span style={{ fontSize: 12, color: "var(--text-2)" }}>
            {pipeline.shipped_count}/{pipeline.total_patterns} patterns shipped
          </span>
        )}
      </nav>

      <div className="page-container">
        <div className="page-header">
          <div>
            <h1 className="page-title">Exception Pipeline</h1>
            <p className="page-subtitle">
              Recurring exception patterns advancing toward automation. Each shipped pattern removes a class of escalation permanently.
            </p>
          </div>
          <button
            className="btn btn-primary"
            onClick={runClustering}
            disabled={clustering}
          >
            {clustering ? "Clustering…" : "Run Clustering"}
          </button>
        </div>

        {error && <div className="error-state" style={{ marginBottom: 20 }}>{error}</div>}

        {pipeline && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
            {stages.map(({ key, label }) => {
              const items = pipeline[key] as Cluster[];
              return (
                <div key={key}>
                  <div style={{ marginBottom: 12, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{label}</span>
                    <span style={{ fontSize: 12, color: "var(--text-2)" }}>{items.length}</span>
                  </div>
                  {items.length === 0 ? (
                    <div style={{ color: "var(--text-2)", fontSize: 12, textAlign: "center", padding: "24px 0", border: "1px dashed var(--border)", borderRadius: "var(--radius)" }}>
                      Empty
                    </div>
                  ) : (
                    items.map((c) => (
                      <ClusterCard key={c.id} cluster={c} workspaceId={id} />
                    ))
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
