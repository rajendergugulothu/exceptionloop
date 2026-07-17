"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type Workspace, type ExceptionCase } from "@/lib/api";

function severityClass(s: string | null) {
  if (!s) return "";
  return `sev-${s}`;
}

function SeverityBadge({ s }: { s: string | null }) {
  const cls = s ? `badge badge-${s}` : "badge badge-neutral";
  return <span className={cls}>{s ?? "—"}</span>;
}

export default function WorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [cases, setCases] = useState<ExceptionCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => {
    Promise.all([api.workspaces.get(id), api.cases.list(id, { limit: 100 })])
      .then(([ws, c]) => { setWorkspace(ws); setCases(c); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  const filtered = statusFilter ? cases.filter((c) => c.status === statusFilter) : cases;
  const openCount = cases.filter((c) => c.status === "open").length;
  const criticalCount = cases.filter((c) => c.severity === "critical").length;
  const resolvedCount = cases.filter((c) => c.status === "resolved").length;

  const severityBars = ["critical", "high", "medium", "low"].map((s) => ({
    s,
    count: cases.filter((c) => c.severity === s).length,
  }));
  const maxCount = Math.max(...severityBars.map((b) => b.count), 1);
  const barColors: Record<string, string> = {
    critical: "var(--red)", high: "var(--orange)", medium: "var(--amber)", low: "var(--teal)",
  };

  if (loading) return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-mark">EL</div>
          <div><div className="sidebar-logo-text">ExceptionLoop</div></div>
        </div>
      </aside>
      <div className="main-content">
        <div className="loading-state" style={{ marginTop: 80 }}>
          <span className="loading-dot"/><span className="loading-dot"/><span className="loading-dot"/>
          <div style={{ marginTop: 12 }}>Loading workspace…</div>
        </div>
      </div>
    </div>
  );

  if (!workspace) return <div className="error-state" style={{ margin: 24 }}>{error}</div>;

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="sidebar-logo-mark">EL</div>
          <div>
            <div className="sidebar-logo-text">ExceptionLoop</div>
            <div className="sidebar-logo-sub">Control Plane</div>
          </div>
        </div>
        <div className="sidebar-section">
          <div className="sidebar-section-label">Navigation</div>
          <Link href="/" className="sidebar-link">
            <svg className="sidebar-link-icon" viewBox="0 0 16 16" fill="none">
              <rect x="1" y="1" width="6" height="6" rx="1.5" fill="currentColor"/>
              <rect x="9" y="1" width="6" height="6" rx="1.5" fill="currentColor" opacity=".4"/>
              <rect x="1" y="9" width="6" height="6" rx="1.5" fill="currentColor" opacity=".4"/>
              <rect x="9" y="9" width="6" height="6" rx="1.5" fill="currentColor" opacity=".4"/>
            </svg>
            Workspaces
          </Link>
          <div className="sidebar-link active">
            <svg className="sidebar-link-icon" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M8 5v3.5l2 1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            Exception Queue
          </div>
          <Link href={`/workspace/${id}/clusters`} className="sidebar-link">
            <svg className="sidebar-link-icon" viewBox="0 0 16 16" fill="none">
              <rect x="1" y="5" width="4" height="6" rx="1" fill="currentColor" opacity=".4"/>
              <rect x="6" y="3" width="4" height="10" rx="1" fill="currentColor"/>
              <rect x="11" y="7" width="4" height="6" rx="1" fill="currentColor" opacity=".4"/>
            </svg>
            Exception Pipeline
          </Link>
        </div>
        <div className="sidebar-section">
          <div className="sidebar-section-label">Quick Stats</div>
          <div style={{ padding: "4px 6px", display: "flex", flexDirection: "column", gap: 8 }}>
            {[
              { label: "Open", value: openCount, color: "var(--amber)" },
              { label: "Critical", value: criticalCount, color: "var(--red)" },
              { label: "Resolved", value: resolvedCount, color: "var(--teal)" },
            ].map(({ label, value, color }) => (
              <div key={label} className="row row-between" style={{ fontSize: 12 }}>
                <span style={{ color: "var(--text-2)" }}>{label}</span>
                <span style={{ fontWeight: 700, color, fontVariantNumeric: "tabular-nums" }}>{value}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="sidebar-bottom">
          <Link href={`/sidebar?workspace_id=${id}`}>
            <button className="btn btn-secondary btn-sm" style={{ width: "100%" }}>
              Zendesk Sidebar Demo →
            </button>
          </Link>
        </div>
      </aside>

      {/* Main */}
      <div className="main-content">
        <div className="topbar">
          <div>
            <div className="topbar-title">{workspace.name}</div>
            <div className="topbar-sub">{workspace.agent_type} agent · {cases.length} total exceptions</div>
          </div>
        </div>

        <div className="page">
          {error && <div className="error-state" style={{ marginBottom: 20 }}>{error}</div>}

          {/* Stat row */}
          <div className="grid-3" style={{ marginBottom: 24 }}>
            <div className="stat-card">
              <div className="stat-value" style={{ color: "var(--amber)" }}>{openCount}</div>
              <div className="stat-label">Open Exceptions</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: "var(--red)" }}>{criticalCount}</div>
              <div className="stat-label">Critical Severity</div>
            </div>
            <div className="stat-card">
              <div className="stat-value" style={{ color: "var(--teal)" }}>{resolvedCount}</div>
              <div className="stat-label">Resolved</div>
            </div>
          </div>

          {/* Severity distribution */}
          <div className="card" style={{ marginBottom: 24 }}>
            <div className="row row-between" style={{ marginBottom: 16 }}>
              <div className="section-heading">Volume by Severity</div>
              <span className="fs-11 text-faint">{cases.length} total</span>
            </div>
            <div style={{ display: "flex", gap: 12, alignItems: "flex-end", height: 72 }}>
              {severityBars.map(({ s, count }) => (
                <div key={s} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: barColors[s], fontVariantNumeric: "tabular-nums" }}>{count}</span>
                  <div style={{
                    width: "100%",
                    height: `${Math.max((count / maxCount) * 48, count > 0 ? 6 : 2)}px`,
                    background: barColors[s],
                    borderRadius: "4px 4px 2px 2px",
                    opacity: count === 0 ? 0.15 : 0.85,
                    transition: "height 0.4s ease",
                  }} />
                  <span style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-3)" }}>{s}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Case queue */}
          <div className="row row-between" style={{ marginBottom: 14 }}>
            <div className="section-heading">Exception Queue</div>
            <div className="row row-8">
              <select
                className="input"
                style={{ width: "auto", padding: "5px 10px", fontSize: 12 }}
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="">All statuses</option>
                <option value="open">Open</option>
                <option value="in_review">In Review</option>
                <option value="resolved">Resolved</option>
              </select>
            </div>
          </div>

          <div className="stack stack-8">
            {filtered.map((c) => (
              <Link key={c.id} href={`/cases/${c.id}`}>
                <div className={`exception-row ${severityClass(c.severity)}`}>
                  <div className="exception-row-body">
                    <div className="exception-row-msg">{c.customer_message}</div>
                    <div className="exception-row-reason">{c.escalation_reason}</div>
                  </div>
                  <div className="exception-row-meta">
                    <SeverityBadge s={c.severity} />
                    <span className="badge badge-neutral">{c.status}</span>
                    {c.exception_type && (
                      <span className="fs-11 text-faint mono">{c.exception_type}</span>
                    )}
                  </div>
                </div>
              </Link>
            ))}
            {filtered.length === 0 && (
              <div className="empty-state">
                <div className="empty-state-icon">✓</div>
                <div style={{ fontWeight: 600, color: "var(--text-2)", marginBottom: 4 }}>All clear</div>
                <div>No exceptions match this filter</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
