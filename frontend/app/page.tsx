"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { UserButton } from "@clerk/nextjs";
import { api, type Workspace } from "@/lib/api";

export default function Home() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    api.workspaces.list()
      .then(setWorkspaces)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function createWorkspace(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const ws = await api.workspaces.create(newName.trim());
      setWorkspaces((p) => [ws, ...p]);
      setNewName("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setCreating(false);
    }
  }

  const totalExceptions = workspaces.reduce((s, w) => s + w.case_count, 0);

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
          <Link href="/" className="sidebar-link active">
            <svg className="sidebar-link-icon" viewBox="0 0 16 16" fill="none">
              <rect x="1" y="1" width="6" height="6" rx="1.5" fill="currentColor"/>
              <rect x="9" y="1" width="6" height="6" rx="1.5" fill="currentColor" opacity=".4"/>
              <rect x="1" y="9" width="6" height="6" rx="1.5" fill="currentColor" opacity=".4"/>
              <rect x="9" y="9" width="6" height="6" rx="1.5" fill="currentColor" opacity=".4"/>
            </svg>
            Workspaces
          </Link>
        </div>

        <div className="sidebar-bottom">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div style={{ fontSize: 11, color: "var(--text-3)", padding: "0 6px" }}>
              {workspaces.length} workspace{workspaces.length !== 1 ? "s" : ""} · {totalExceptions} exceptions
            </div>
            <UserButton afterSignOutUrl="/sign-in" />
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="main-content">
        <div className="topbar">
          <div>
            <div className="topbar-title">Workspaces</div>
            <div className="topbar-sub">Each workspace monitors a distinct AI agent deployment</div>
          </div>
          <div className="topbar-spacer" />
        </div>

        <div className="page">
          {/* Create workspace */}
          <form onSubmit={createWorkspace} style={{ display: "flex", gap: 10, marginBottom: 28, maxWidth: 520 }}>
            <input
              className="input"
              placeholder="e.g. QuickCommerce Returns Agent"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <button className="btn btn-primary" type="submit" disabled={creating || !newName.trim()} style={{ flexShrink: 0 }}>
              {creating ? "Creating…" : "New Workspace"}
            </button>
          </form>

          {error && <div className="error-state" style={{ marginBottom: 20 }}>{error}</div>}

          {loading ? (
            <div className="loading-state">
              <div style={{ marginBottom: 12 }}>
                <span className="loading-dot" />
                <span className="loading-dot" />
                <span className="loading-dot" />
              </div>
              Loading workspaces…
            </div>
          ) : (
            <div className="stack stack-8">
              {workspaces.map((ws) => (
                <Link key={ws.id} href={`/workspace/${ws.id}`}>
                  <div className="workspace-card">
                    <div className="workspace-icon">
                      {ws.agent_type === "support" ? "🎧" : ws.agent_type === "finance" ? "💳" : ws.agent_type === "operations" ? "⚙️" : "🤖"}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div className="workspace-name">{ws.name}</div>
                      <div className="workspace-meta">
                        {ws.agent_type} agent
                        {ws.case_count > 0 && (
                          <> · <span style={{ color: ws.case_count > 10 ? "var(--amber)" : "var(--text-2)" }}>{ws.case_count} exception{ws.case_count !== 1 ? "s" : ""}</span></>
                        )}
                        {ws.case_count === 0 && " · No exceptions yet"}
                      </div>
                    </div>
                    <div className="workspace-arrow">→</div>
                  </div>
                </Link>
              ))}
              {workspaces.length === 0 && !loading && (
                <div className="empty-state">
                  <div className="empty-state-icon">⚡</div>
                  <div style={{ fontWeight: 600, color: "var(--text-2)", marginBottom: 6 }}>No workspaces yet</div>
                  <div>Create one above to start capturing agent exceptions</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
