const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "https://exceptionloop.onrender.com";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json() as Promise<T>;
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface Workspace {
  id: string;
  name: string;
  agent_type: string;
  created_by: string | null;
  created_at: string;
  case_count: number;
}

export interface ExceptionCase {
  id: string;
  workspace_id: string;
  source: string;
  intake_mode: string;
  customer_message: string;
  escalation_reason: string;
  exception_type: string | null;
  severity: string | null;
  sla_tier: string | null;
  recommended_owner: string | null;
  status: string;
  zendesk_ticket_id: string | null;
  received_at: string;
}

export interface SimilarCase {
  rank: number;
  case_id: string;
  customer_message: string;
  exception_type: string | null;
  severity: string | null;
  resolution: string;
  similarity_score: number;
}

export interface Recommendation {
  id: string;
  exception_case_id: string;
  proposed_steps: string;
  evidence_summary: string | null;
  similar_case_ids: string[];
  confidence_score: number | null;
  uncertainty_notes: string | null;
  generated_at: string;
}

export interface Resolution {
  id: string;
  exception_case_id: string;
  verdict: string;
  action_taken: string;
  usefulness_rating: number | null;
  resolved_by: string;
  resolved_at: string;
  entered_pipeline: boolean;
}

export interface QualityReview {
  id: string;
  resolution_id: string;
  triggered_by: string;
  reviewer: string | null;
  decision: string | null;
  notes: string | null;
  reviewed_at: string | null;
}

export interface NewPatternFlag {
  id: string;
  exception_case_id: string;
  flagged_by: string;
  occurrence_count: number;
  status: string;
  flagged_at: string;
}

export interface Cluster {
  id: string;
  workspace_id: string;
  label: string;
  case_count: number;
  purity_score: number | null;
  resolution_consistency: number | null;
  status: string;
  first_seen_at: string | null;
  last_seen_at: string | null;
}

export interface ReadinessScore {
  id: string;
  cluster_id: string;
  frequency_score: number | null;
  consistency_score: number | null;
  data_completeness_score: number | null;
  risk_score: number | null;
  reversibility_score: number | null;
  policy_clarity_score: number | null;
  integration_stability_score: number | null;
  evaluation_feasibility_score: number | null;
  total_score: number | null;
  blockers: string[];
  scored_at: string;
}

export interface WorkflowSpec {
  id: string;
  cluster_id: string;
  trigger: string;
  required_inputs: string[];
  steps: { description: string; source_case_ids: string[] }[];
  edge_cases: string | null;
  test_cases: string | null;
  rollback_trigger: string | null;
  pipeline_stage: string;
  approved_by: string | null;
  approved_at: string | null;
  deployed_at: string | null;
}

export interface PipelineView {
  candidates: Cluster[];
  approved: Cluster[];
  in_development: Cluster[];
  shipped: Cluster[];
  total_patterns: number;
  shipped_count: number;
}

export interface EnrichmentResponse {
  case_id: string;
  exception_type: string | null;
  severity: string | null;
  sla_tier: string | null;
  similar_cases_found: number;
  recommendation_confidence: number | null;
  proposed_steps: string | null;
  uncertainty_notes: string | null;
  message: string;
}

// ── API client ─────────────────────────────────────────────────────────────

export const api = {
  workspaces: {
    list: () => request<Workspace[]>("/workspaces/"),
    get: (id: string) => request<Workspace>(`/workspaces/${id}`),
    create: (name: string, agentType = "support", createdBy?: string) =>
      request<Workspace>("/workspaces/", {
        method: "POST",
        body: JSON.stringify({ name, agent_type: agentType, created_by: createdBy }),
      }),
  },

  cases: {
    list: (workspaceId: string, params?: { status?: string; severity?: string; limit?: number }) => {
      const q = new URLSearchParams();
      if (params?.status) q.set("status", params.status);
      if (params?.severity) q.set("severity", params.severity);
      if (params?.limit) q.set("limit", String(params.limit));
      return request<ExceptionCase[]>(`/workspaces/${workspaceId}/cases?${q}`);
    },
    get: (id: string) => request<ExceptionCase>(`/cases/${id}`),
    intake: (payload: {
      workspace_id: string;
      customer_message: string;
      escalation_reason: string;
      agent_trace?: string;
      attempted_actions?: string;
      missing_information?: string;
      policy_reference?: string;
    }) =>
      request<{ exception_case: ExceptionCase; message: string; next_step: string }>("/intake/full", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },

  enrichment: {
    enrich: (caseId: string) =>
      request<EnrichmentResponse>(`/enrich/${caseId}`, { method: "POST" }),
    similar: (caseId: string) => request<SimilarCase[]>(`/cases/${caseId}/similar`),
    recommendation: (caseId: string) => request<Recommendation>(`/cases/${caseId}/recommendation`),
  },

  resolutions: {
    resolve: (caseId: string, payload: {
      verdict: "approved" | "edited" | "rejected";
      action_taken: string;
      resolved_by: string;
      resolution_notes?: string;
      edit_delta?: string;
      usefulness_rating?: number;
    }) =>
      request<Resolution>(`/cases/${caseId}/resolve`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    flagNewPattern: (caseId: string, flaggedBy: string) =>
      request<NewPatternFlag>(`/cases/${caseId}/flag-new-pattern`, {
        method: "POST",
        body: JSON.stringify({ flagged_by: flaggedBy }),
      }),
    qualityReviews: (workspaceId: string) =>
      request<QualityReview[]>(`/workspaces/${workspaceId}/quality-reviews`),
    adjudicate: (reviewId: string, reviewer: string, decision: string, notes?: string) =>
      request<QualityReview>(`/quality-reviews/${reviewId}/adjudicate`, {
        method: "POST",
        body: JSON.stringify({ reviewer, decision, notes }),
      }),
    newPatternFlags: (workspaceId: string) =>
      request<NewPatternFlag[]>(`/workspaces/${workspaceId}/new-pattern-flags`),
  },

  clusters: {
    run: (workspaceId: string) =>
      request<Cluster[]>(`/workspaces/${workspaceId}/cluster`, { method: "POST" }),
    list: (workspaceId: string) => request<Cluster[]>(`/workspaces/${workspaceId}/clusters`),
    get: (id: string) => request<Cluster>(`/clusters/${id}`),
    purityReview: (clusterId: string, reviewer: string, purityScore: number, notes?: string) =>
      request<Cluster>(`/clusters/${clusterId}/purity-review`, {
        method: "POST",
        body: JSON.stringify({ reviewer, purity_score: purityScore, notes }),
      }),
    scoreReadiness: (clusterId: string) =>
      request<ReadinessScore>(`/clusters/${clusterId}/score-readiness`, { method: "POST" }),
    getReadiness: (clusterId: string) =>
      request<ReadinessScore>(`/clusters/${clusterId}/readiness`),
    generateSpec: (clusterId: string) =>
      request<WorkflowSpec>(`/clusters/${clusterId}/generate-spec`, { method: "POST" }),
    getSpec: (clusterId: string) => request<WorkflowSpec>(`/clusters/${clusterId}/spec`),
    advancePipeline: (specId: string, actor: string, newStage: string) =>
      request<WorkflowSpec>(`/specs/${specId}/advance`, {
        method: "POST",
        body: JSON.stringify({ actor, new_stage: newStage }),
      }),
    pipeline: (workspaceId: string) =>
      request<PipelineView>(`/workspaces/${workspaceId}/pipeline`),
  },
};
