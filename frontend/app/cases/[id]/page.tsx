"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type ExceptionCase, type SimilarCase, type Recommendation } from "@/lib/api";

function parseSteps(text: string): string[] {
  return text.split(/\n/).map((l) => l.replace(/^\d+\.\s*/, "").trim()).filter(Boolean);
}

export default function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [caseData, setCaseData] = useState<ExceptionCase | null>(null);
  const [similar, setSimilar] = useState<SimilarCase[]>([]);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [loading, setLoading] = useState(true);
  const [enriching, setEnriching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ verdict: "approved" as "approved"|"edited"|"rejected", action_taken: "", resolved_by: "", usefulness_rating: 5 });
  const [submitting, setSubmitting] = useState(false);
  const [resolved, setResolved] = useState(false);

  useEffect(() => {
    api.cases.get(id)
      .then((c) => {
        setCaseData(c);
        return Promise.all([
          api.enrichment.similar(id).catch(() => []),
          api.enrichment.recommendation(id).catch(() => null),
        ]);
      })
      .then(([s, r]) => { setSimilar(s); setRec(r); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  async function enrich() {
    setEnriching(true); setError(null);
    try {
      await api.enrichment.enrich(id);
      const [s, r, c] = await Promise.all([
        api.enrichment.similar(id),
        api.enrichment.recommendation(id),
        api.cases.get(id),
      ]);
      setSimilar(s); setRec(r); setCaseData(c);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Enrichment failed"); }
    finally { setEnriching(false); }
  }

  async function resolve(verdict: "approved"|"edited"|"rejected") {
    if (!form.resolved_by.trim() || !form.action_taken.trim()) { setError("Email and action taken are required."); return; }
    setSubmitting(true); setError(null);
    try {
      await api.resolutions.resolve(id, {
        verdict,
        action_taken: form.action_taken,
        resolved_by: form.resolved_by,
        usefulness_rating: verdict === "rejected" ? form.usefulness_rating : undefined,
      });
      setResolved(true);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Failed"); }
    finally { setSubmitting(false); }
  }

  const severityColor: Record<string, string> = {
    critical: "var(--red)", high: "var(--orange)", medium: "var(--amber)", low: "var(--teal)",
  };

  const confidence = rec?.confidence_score ?? null;
  const confColor = confidence === null ? "var(--text-3)" : confidence >= 0.8 ? "var(--teal)" : confidence >= 0.6 ? "var(--amber)" : "var(--red)";

  if (loading) return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
      <div className="loading-state">
        <span className="loading-dot"/><span className="loading-dot"/><span className="loading-dot"/>
        <div style={{ marginTop: 12 }}>Loading case…</div>
      </div>
    </div>
  );
  if (!caseData) return <div className="error-state" style={{ margin: 24 }}>{error}</div>;

  const steps = rec ? parseSteps(rec.proposed_steps) : [];

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
          <Link href={`/workspace/${caseData.workspace_id}`} className="sidebar-link">
            <svg className="sidebar-link-icon" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M8 5v3.5l2 1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            Exception Queue
          </Link>
        </div>
        {caseData.exception_type && (
          <div className="sidebar-section">
            <div className="sidebar-section-label">This Case</div>
            <div style={{ padding: "4px 6px", display: "flex", flexDirection: "column", gap: 8 }}>
              {[
                { label: "Type", value: caseData.exception_type },
                { label: "Severity", value: caseData.severity, color: caseData.severity ? severityColor[caseData.severity] : undefined },
                { label: "SLA", value: caseData.sla_tier },
                { label: "Owner", value: caseData.recommended_owner },
              ].map(({ label, value, color }) => (
                <div key={label} style={{ fontSize: 12 }}>
                  <div style={{ color: "var(--text-3)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 700, marginBottom: 2 }}>{label}</div>
                  <div style={{ fontWeight: 600, color: color ?? "var(--text)" }}>{value ?? "—"}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </aside>

      {/* Main */}
      <div className="main-content">
        <div className="topbar">
          <Link href={`/workspace/${caseData.workspace_id}`} style={{ color: "var(--text-3)", fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
            ← Queue
          </Link>
          <div style={{ width: 1, height: 16, background: "var(--border)" }} />
          <div>
            <div className="topbar-title">{caseData.exception_type ?? "Unclassified Exception"}</div>
          </div>
          <div className="topbar-spacer" />
          {caseData.severity && (
            <span className={`badge badge-${caseData.severity}`}>{caseData.severity}</span>
          )}
          <span className="badge badge-neutral">{caseData.status}</span>
        </div>

        <div className="page" style={{ maxWidth: 760 }}>
          {error && <div className="error-state" style={{ marginBottom: 20 }}>{error}</div>}

          {/* 1. Customer message */}
          <div className="card" style={{ marginBottom: 14 }}>
            <div className="label" style={{ marginBottom: 10 }}>Customer Message</div>
            <p style={{ lineHeight: 1.7, color: "var(--text)" }}>{caseData.customer_message}</p>
            <div className="divider" />
            <div className="label" style={{ marginBottom: 8 }}>Escalation Reason</div>
            <p style={{ color: "var(--text-2)", lineHeight: 1.65, fontSize: 12 }}>{caseData.escalation_reason}</p>
          </div>

          {/* 2. Classification */}
          <div className="card" style={{ marginBottom: 14 }}>
            <div className="row row-between" style={{ marginBottom: 14 }}>
              <div className="label">Classification & Context</div>
              {!caseData.exception_type && (
                <button className="btn btn-primary btn-sm" onClick={enrich} disabled={enriching}>
                  {enriching ? "Running enrichment…" : "Run Enrichment"}
                </button>
              )}
            </div>
            <div className="grid-2" style={{ gap: 16 }}>
              {[
                { label: "Exception Type", value: caseData.exception_type, mono: true },
                { label: "Severity", value: caseData.severity, color: caseData.severity ? severityColor[caseData.severity] : undefined },
                { label: "SLA Tier", value: caseData.sla_tier },
                { label: "Recommended Owner", value: caseData.recommended_owner, mono: true },
              ].map(({ label, value, color, mono }) => (
                <div key={label}>
                  <div className="label" style={{ marginBottom: 4 }}>{label}</div>
                  <div style={{ fontWeight: 600, color: color ?? "var(--text)", fontFamily: mono ? "var(--font-mono)" : undefined, fontSize: mono ? 12 : 13 }}>
                    {value ?? <span className="text-faint">—</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 3. Similar cases */}
          {similar.length > 0 && (
            <div className="card" style={{ marginBottom: 14 }}>
              <div className="label" style={{ marginBottom: 12 }}>Similar Resolved Cases — {similar.length} found</div>
              <div className="stack stack-8">
                {similar.map((s, i) => (
                  <div key={s.case_id} className="similar-card">
                    <div className="row row-between" style={{ marginBottom: 6 }}>
                      <div className="row row-8">
                        <span className="fs-11 text-faint">#{i + 1}</span>
                        <span className={`badge badge-${s.severity ?? "neutral"}`}>{s.exception_type ?? "unknown"}</span>
                      </div>
                      <span className="similar-match">{Math.round(s.similarity_score * 100)}% match</span>
                    </div>
                    <p style={{ fontSize: 12, color: "var(--text-2)", marginBottom: 6, fontStyle: "italic" }}>
                      "{s.customer_message.slice(0, 100)}{s.customer_message.length > 100 ? "…" : ""}"
                    </p>
                    <div style={{ fontSize: 12 }}>
                      <span className="text-faint">Resolution: </span>
                      <span style={{ fontWeight: 500 }}>{s.resolution}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 4. Recommendation */}
          {rec && (
            <div className="card" style={{ marginBottom: 14 }}>
              <div className="row row-between" style={{ marginBottom: 4 }}>
                <div className="label">AI Recommendation</div>
                {confidence !== null && (
                  <span style={{ fontSize: 12, fontWeight: 700, color: confColor, fontVariantNumeric: "tabular-nums" }}>
                    {Math.round(confidence * 100)}% confidence
                  </span>
                )}
              </div>
              {confidence !== null && (
                <div className="confidence-bar" style={{ marginBottom: 16 }}>
                  <div className="confidence-fill" style={{ width: `${Math.round(confidence * 100)}%`, background: confColor }} />
                </div>
              )}
              <div>
                {steps.length > 0 ? steps.map((step, i) => (
                  <div key={i} className="rec-step">
                    <div className="rec-step-num">{i + 1}</div>
                    <div className="rec-step-text">{step}</div>
                  </div>
                )) : (
                  <p style={{ lineHeight: 1.7, color: "var(--text)" }}>{rec.proposed_steps}</p>
                )}
              </div>
              {rec.uncertainty_notes && (
                <>
                  <div className="divider" />
                  <div style={{ display: "flex", gap: 8, padding: "8px 10px", background: "var(--amber-dim)", borderRadius: "var(--radius-sm)", border: "1px solid rgba(245,166,35,0.2)" }}>
                    <span style={{ fontSize: 13 }}>⚠</span>
                    <p style={{ fontSize: 12, color: "var(--amber)", lineHeight: 1.6 }}>{rec.uncertainty_notes}</p>
                  </div>
                </>
              )}
              {rec.evidence_summary && (
                <p style={{ marginTop: 12, fontSize: 12, color: "var(--text-3)" }}>
                  <strong style={{ color: "var(--text-2)" }}>Evidence: </strong>{rec.evidence_summary}
                </p>
              )}
            </div>
          )}

          {/* 5. Actions */}
          {!resolved ? (
            <div className="card">
              <div className="label" style={{ marginBottom: 16 }}>Resolve This Exception</div>
              <div className="stack stack-14" style={{ "--stack-gap": "14px" } as React.CSSProperties}>
                <div>
                  <div className="label" style={{ marginBottom: 6 }}>Your email</div>
                  <input className="input" placeholder="specialist@company.com" value={form.resolved_by}
                    onChange={(e) => setForm((f) => ({ ...f, resolved_by: e.target.value }))} />
                </div>
                <div>
                  <div className="label" style={{ marginBottom: 6 }}>Action taken</div>
                  <textarea className="input" rows={3}
                    placeholder="Describe what you did to resolve this exception…"
                    value={form.action_taken}
                    onChange={(e) => setForm((f) => ({ ...f, action_taken: e.target.value }))}
                    style={{ resize: "vertical" }} />
                </div>
                {form.verdict === "rejected" && (
                  <div>
                    <div className="label" style={{ marginBottom: 6 }}>Usefulness of similar cases shown (1–5)</div>
                    <input className="input" type="number" min={1} max={5} value={form.usefulness_rating}
                      onChange={(e) => setForm((f) => ({ ...f, usefulness_rating: Number(e.target.value) }))} style={{ maxWidth: 100 }} />
                  </div>
                )}
                <div className="row row-8" style={{ marginTop: 4, flexWrap: "wrap" }}>
                  <button className="btn btn-primary" onClick={() => resolve("approved")} disabled={submitting}>
                    Approve Recommendation
                  </button>
                  <button className="btn btn-secondary" onClick={() => resolve("edited")} disabled={submitting}>
                    Approve with Edits
                  </button>
                  <button className="btn btn-danger" onClick={() => { setForm((f) => ({ ...f, verdict: "rejected" })); resolve("rejected"); }} disabled={submitting}>
                    Reject
                  </button>
                  <button className="btn btn-ghost" onClick={() => api.resolutions.flagNewPattern(id, form.resolved_by || "specialist").then(() => alert("Flagged as new pattern"))} disabled={submitting}>
                    Flag New Pattern
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="card" style={{ textAlign: "center", padding: "48px 0" }}>
              <div style={{ width: 48, height: 48, borderRadius: "50%", background: "var(--teal-dim)", border: "2px solid var(--teal)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px", fontSize: 20, color: "var(--teal)" }}>✓</div>
              <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 6 }}>Exception Resolved</div>
              <div className="text-muted" style={{ marginBottom: 20 }}>Resolution recorded and quality gate applied.</div>
              <Link href={`/workspace/${caseData.workspace_id}`}>
                <button className="btn btn-secondary">Back to Queue</button>
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
