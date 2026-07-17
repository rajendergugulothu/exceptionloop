"use client";
import { Suspense } from "react";
/**
 * Zendesk Sidebar Simulation
 *
 * Accessed at /sidebar?case_id={id} or /sidebar?workspace_id={id}
 *
 * Display order (hard requirement):
 *   1. Customer message
 *   2. Agent context (classification)
 *   3. Similar cases
 *   4. AI recommendation
 *   5. Action buttons
 *
 * Keyboard shortcuts:
 *   Tab    — next case (workspace mode)
 *   Enter  — approve recommendation
 *   Escape — reject recommendation
 *   N      — flag new pattern
 */

import { useEffect, useState, useCallback, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { api, type ExceptionCase, type SimilarCase, type Recommendation } from "@/lib/api";

type Phase = "loading" | "ready" | "enriching" | "resolved" | "error";

function SidebarContent() {
  const params = useSearchParams();
  const caseId = params.get("case_id");
  const workspaceId = params.get("workspace_id");

  const [cases, setCases] = useState<ExceptionCase[]>([]);
  const [caseIndex, setCaseIndex] = useState(0);
  const [currentCase, setCurrentCase] = useState<ExceptionCase | null>(null);
  const [similar, setSimilar] = useState<SimilarCase[]>([]);
  const [rec, setRec] = useState<Recommendation | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);
  const [specialist, setSpecialist] = useState("specialist@company.com");
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const resolvedRef = useRef(false);

  // Load a single case + its enrichment data
  const loadCase = useCallback(async (c: ExceptionCase) => {
    setCurrentCase(c);
    setSimilar([]);
    setRec(null);
    setPhase("enriching");
    resolvedRef.current = false;
    setActionMsg(null);
    setError(null);

    try {
      // Try fetching existing enrichment first
      const [s, r] = await Promise.all([
        api.enrichment.similar(c.id).catch(() => []),
        api.enrichment.recommendation(c.id).catch(() => null),
      ]);

      if (s.length === 0 && !r) {
        // Cold start — run enrichment
        await api.enrichment.enrich(c.id);
        const [s2, r2] = await Promise.all([
          api.enrichment.similar(c.id).catch(() => []),
          api.enrichment.recommendation(c.id).catch(() => null),
        ]);
        setSimilar(s2);
        setRec(r2);
        const updated = await api.cases.get(c.id);
        setCurrentCase(updated);
      } else {
        setSimilar(s);
        setRec(r);
        if (!c.exception_type) {
          const updated = await api.cases.get(c.id);
          setCurrentCase(updated);
        }
      }
      setPhase("ready");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Enrichment failed");
      setPhase("error");
    }
  }, []);

  // Initial data load
  useEffect(() => {
    async function init() {
      setPhase("loading");
      try {
        if (caseId) {
          const c = await api.cases.get(caseId);
          setCases([c]);
          setCaseIndex(0);
          await loadCase(c);
        } else if (workspaceId) {
          const all = await api.cases.list(workspaceId, { status: "open", limit: 50 });
          setCases(all);
          setCaseIndex(0);
          if (all.length > 0) {
            await loadCase(all[0]);
          } else {
            setPhase("ready");
          }
        } else {
          setError("Provide ?case_id= or ?workspace_id= in the URL");
          setPhase("error");
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load");
        setPhase("error");
      }
    }
    init();
  }, [caseId, workspaceId, loadCase]);

  // Approve recommendation
  const approve = useCallback(async () => {
    if (!currentCase || resolvedRef.current) return;
    resolvedRef.current = true;
    setPhase("loading");
    try {
      await api.resolutions.resolve(currentCase.id, {
        verdict: "approved",
        action_taken: rec?.proposed_steps ?? "Approved AI recommendation",
        resolved_by: specialist,
      });
      setActionMsg("Approved — moving to next case");
      setPhase("resolved");
      setTimeout(() => advanceCase(), 1200);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
      setPhase("ready");
      resolvedRef.current = false;
    }
  }, [currentCase, rec, specialist]);

  // Reject recommendation
  const reject = useCallback(async () => {
    if (!currentCase || resolvedRef.current) return;
    resolvedRef.current = true;
    setPhase("loading");
    try {
      await api.resolutions.resolve(currentCase.id, {
        verdict: "rejected",
        action_taken: "Rejected — specialist will handle manually",
        resolved_by: specialist,
        usefulness_rating: 3,
      });
      setActionMsg("Rejected — moving to next case");
      setPhase("resolved");
      setTimeout(() => advanceCase(), 1200);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed");
      setPhase("ready");
      resolvedRef.current = false;
    }
  }, [currentCase, specialist]);

  // Flag as new pattern
  const flagPattern = useCallback(async () => {
    if (!currentCase) return;
    await api.resolutions.flagNewPattern(currentCase.id, specialist);
    setActionMsg("Flagged as new pattern");
    setTimeout(() => setActionMsg(null), 2000);
  }, [currentCase, specialist]);

  // Advance to next case in workspace queue
  const advanceCase = useCallback(async () => {
    if (cases.length === 0) return;
    const nextIdx = caseIndex + 1;
    if (nextIdx >= cases.length) {
      setPhase("ready");
      setCurrentCase(null);
      setActionMsg("All open exceptions reviewed.");
      return;
    }
    setCaseIndex(nextIdx);
    await loadCase(cases[nextIdx]);
  }, [cases, caseIndex, loadCase]);

  // Keyboard shortcuts
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (phase !== "ready") return;
      if (e.key === "Tab") { e.preventDefault(); advanceCase(); }
      if (e.key === "Enter") { e.preventDefault(); approve(); }
      if (e.key === "Escape") { e.preventDefault(); reject(); }
      if (e.key === "n" || e.key === "N") { e.preventDefault(); flagPattern(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, approve, reject, flagPattern, advanceCase]);

  const severityColor: Record<string, string> = {
    critical: "var(--red)", high: "var(--orange)", medium: "var(--amber)", low: "var(--teal)",
  };

  return (
    <div className="sidebar-widget">
      {/* Header */}
      <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", background: "var(--surface)", flexShrink: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontWeight: 700, color: "var(--accent)", fontSize: 14 }}>ExceptionLoop</span>
          {cases.length > 1 && (
            <span style={{ fontSize: 11, color: "var(--text-2)" }}>
              {caseIndex + 1} / {cases.length}
            </span>
          )}
        </div>
        <div style={{ fontSize: 11, color: "var(--text-2)", marginTop: 2 }}>
          AI Exception Control Panel
        </div>
      </div>

      {/* Specialist input */}
      <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--border)", background: "var(--surface)" }}>
        <input
          className="input"
          style={{ fontSize: 12, padding: "5px 10px" }}
          placeholder="Your email"
          value={specialist}
          onChange={(e) => setSpecialist(e.target.value)}
        />
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflow: "auto", padding: "16px" }}>
        {(phase === "loading" || phase === "enriching") && (
          <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-2)" }}>
            {phase === "enriching" ? "Classifying + retrieving similar cases…" : "Loading…"}
          </div>
        )}

        {phase === "error" && (
          <div className="error-state">{error}</div>
        )}

        {phase === "resolved" && (
          <div style={{ textAlign: "center", padding: "40px 0" }}>
            <div style={{ fontSize: 28, marginBottom: 8 }}>✓</div>
            <div style={{ color: "var(--teal)", fontWeight: 600 }}>{actionMsg}</div>
          </div>
        )}

        {(phase === "ready") && !currentCase && (
          <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-2)" }}>
            {actionMsg ?? "No open exceptions in this workspace."}
          </div>
        )}

        {phase === "ready" && currentCase && (
          <>
            {actionMsg && (
              <div style={{ background: "var(--surface-2)", borderRadius: 6, padding: "6px 10px", marginBottom: 12, fontSize: 12, color: "var(--teal)" }}>
                {actionMsg}
              </div>
            )}

            {/* 1. Customer message */}
            <div style={{ marginBottom: 14 }}>
              <div className="label">Customer Message</div>
              <div style={{ marginTop: 8, lineHeight: 1.6, fontSize: 13 }}>{currentCase.customer_message}</div>
              <div style={{ marginTop: 8, fontSize: 12, color: "var(--text-2)", fontStyle: "italic" }}>
                {currentCase.escalation_reason}
              </div>
            </div>

            <div className="divider" />

            {/* 2. Agent context */}
            <div style={{ marginBottom: 14 }}>
              <div className="label">Agent Classification</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 8 }}>
                <div style={{ background: "var(--surface-2)", borderRadius: 6, padding: "8px 10px" }}>
                  <div style={{ fontSize: 10, color: "var(--text-2)", marginBottom: 2 }}>TYPE</div>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{currentCase.exception_type ?? "—"}</div>
                </div>
                <div style={{ background: "var(--surface-2)", borderRadius: 6, padding: "8px 10px" }}>
                  <div style={{ fontSize: 10, color: "var(--text-2)", marginBottom: 2 }}>SEVERITY</div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: currentCase.severity ? severityColor[currentCase.severity] : undefined }}>
                    {currentCase.severity ?? "—"}
                  </div>
                </div>
                <div style={{ background: "var(--surface-2)", borderRadius: 6, padding: "8px 10px" }}>
                  <div style={{ fontSize: 10, color: "var(--text-2)", marginBottom: 2 }}>SLA</div>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{currentCase.sla_tier ?? "—"}</div>
                </div>
                <div style={{ background: "var(--surface-2)", borderRadius: 6, padding: "8px 10px" }}>
                  <div style={{ fontSize: 10, color: "var(--text-2)", marginBottom: 2 }}>OWNER</div>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{currentCase.recommended_owner ?? "—"}</div>
                </div>
              </div>
            </div>

            <div className="divider" />

            {/* 3. Similar cases */}
            {similar.length > 0 && (
              <>
                <div style={{ marginBottom: 14 }}>
                  <div className="label">Similar Resolved Cases</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
                    {similar.slice(0, 3).map((s) => (
                      <div key={s.case_id} style={{ background: "var(--surface-2)", borderRadius: 6, padding: "8px 10px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                          <span style={{ fontSize: 10, color: "var(--accent)", fontWeight: 600 }}>
                            {s.exception_type ?? "unknown"}
                          </span>
                          <span style={{ fontSize: 10, color: "var(--text-2)" }}>
                            {Math.round(s.similarity_score * 100)}% match
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: "var(--text-2)", marginBottom: 4 }}>
                          "{s.customer_message.slice(0, 80)}{s.customer_message.length > 80 ? "…" : ""}"
                        </div>
                        <div style={{ fontSize: 11 }}>
                          <span style={{ color: "var(--text-2)" }}>Resolved: </span>
                          {s.resolution.slice(0, 80)}{s.resolution.length > 80 ? "…" : ""}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="divider" />
              </>
            )}

            {/* 4. Recommendation */}
            {rec && (
              <>
                <div style={{ marginBottom: 14 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div className="label">AI Recommendation</div>
                    {rec.confidence_score !== null && (
                      <span style={{ fontSize: 10, color: "var(--text-2)" }}>
                        {Math.round(rec.confidence_score * 100)}% confidence
                      </span>
                    )}
                  </div>
                  <div style={{ marginTop: 8, fontSize: 13, lineHeight: 1.65, whiteSpace: "pre-wrap" }}>
                    {rec.proposed_steps}
                  </div>
                  {rec.uncertainty_notes && (
                    <div style={{ marginTop: 8, fontSize: 11, color: "var(--amber)", background: "var(--amber-dim)", borderRadius: 4, padding: "4px 8px" }}>
                      {rec.uncertainty_notes}
                    </div>
                  )}
                </div>
                <div className="divider" />
              </>
            )}

            {/* 5. Action buttons */}
            <div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <button className="btn btn-primary" onClick={approve} style={{ width: "100%", justifyContent: "center" }}>
                  Approve <span className="kbd">↵</span>
                </button>
                <button className="btn btn-secondary" onClick={reject} style={{ width: "100%", justifyContent: "center" }}>
                  Reject <span className="kbd">Esc</span>
                </button>
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="btn btn-ghost" onClick={flagPattern} style={{ flex: 1, justifyContent: "center" }}>
                    Flag Pattern <span className="kbd">N</span>
                  </button>
                  {cases.length > 1 && (
                    <button className="btn btn-ghost" onClick={advanceCase} style={{ flex: 1, justifyContent: "center" }}>
                      Skip <span className="kbd">Tab</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Keyboard shortcut legend */}
              <div style={{ marginTop: 16, padding: "10px", background: "var(--surface-2)", borderRadius: 6 }}>
                <div style={{ fontSize: 10, color: "var(--text-2)", fontWeight: 600, marginBottom: 6 }}>KEYBOARD SHORTCUTS</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                  {[
                    ["↵ Enter", "Approve recommendation"],
                    ["Esc", "Reject recommendation"],
                    ["N", "Flag new pattern"],
                    ["Tab", "Next case"],
                  ].map(([key, desc]) => (
                    <div key={key} style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                      <span className="kbd">{key}</span>
                      <span style={{ color: "var(--text-2)" }}>{desc}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function SidebarPage() {
  return (
    <Suspense fallback={<div className="sidebar-widget" style={{ padding: 24, color: "var(--text-2)" }}>Loading…</div>}>
      <SidebarContent />
    </Suspense>
  );
}
