export type Job = {
  id: string;
  title: string;
  company: string | null;
  location: string | null;
  country: string;
  remote_type: string | null;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  contract_duration: string | null;
  contract_worker_type: string | null;
  description: string | null;
  requirements: string | null;
  responsibilities: string | null;
  posting_date: string | null;
  source: string;
  source_url: string | null;
  application_url: string | null;
  first_seen_at: string;
  last_seen_at: string;
};

export type JobsResponse = {
  jobs: Job[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function getJobs(params: {
  search?: string;
  employment_type?: string;
  remote_type?: string;
  location?: string;
  page?: number;
  page_size?: number;
} = {}): Promise<JobsResponse> {
  const searchParams = new URLSearchParams();

  if (params.search) {
    searchParams.set("search", params.search);
  }

  if (params.employment_type) {
    searchParams.set("employment_type", params.employment_type);
  }

  if (params.remote_type) {
    searchParams.set("remote_type", params.remote_type);
  }

  if (params.location) {
    searchParams.set("location", params.location);
  }

  searchParams.set("page", String(params.page ?? 1));
  searchParams.set("page_size", String(params.page_size ?? 20));

  const response = await fetch(
    `${API_BASE_URL}/jobs?${searchParams.toString()}`,
    {
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch jobs: ${response.status}`);
  }

  return response.json();
}
export type SkillEvidence = {
  skill: string;
  status: "matched" | "missing" | "uncertain";
  evidence_type:
    | "explicit"
    | "experience"
    | "project"
    | "education"
    | "inferred"
    | "none";
  evidence: string | null;
};

export type MatchComponent = {
  name: string;
  score: number;
  max_score: number;
  explanation: string;
};

export type JobMatchResult = {
  id: string;
  job_id: string;
  resume_version_id: string;
  job_intelligence_id: string | null;
  score: number;
  confidence: string;
  engine_version: string;
  strengths: string[];
  skill_gaps: string[];
  components: MatchComponent[];
  must_have_matches: SkillEvidence[];
  must_have_gaps: SkillEvidence[];
  preferred_matches: SkillEvidence[];
  preferred_gaps: SkillEvidence[];
};

export type JobIntelligenceSkill = {
  canonical_skill: string;
  level: "required" | "preferred";
  evidence_text: string;
  confidence: "high" | "medium" | "low";
};

export type JobIntelligenceExperience = {
  level: "required" | "preferred";
  minimum_years: number | null;
  maximum_years: number | null;
  area: string | null;
  context: string | null;
  evidence_text: string;
  confidence: "high" | "medium" | "low";
};

export type JobIntelligenceEducation = {
  level: "required" | "preferred";
  degree_level: string | null;
  field_of_study: string | null;
  evidence_text: string;
  confidence: "high" | "medium" | "low";
};

export type JobIntelligenceCertification = {
  level: "required" | "preferred";
  name: string;
  evidence_text: string;
  confidence: "high" | "medium" | "low";
};

export type JobIntelligenceResponsibility = {
  description: string;
  evidence_text: string;
};

export type JobIntelligenceData = {
  identity: {
    original_title: string;
    normalized_title: string | null;
    role_family: string | null;
    seniority: string | null;
  };
  employment: {
    employment_type: string;
    evidence_text: string | null;
  };
  location: {
    raw_location: string | null;
    city: string | null;
    state: string | null;
    country: string | null;
    additional_locations: string[];
    remote_type: string;
    work_arrangement_text: string | null;
    relocation_mentioned: boolean;
  };
  required_skills: JobIntelligenceSkill[];
  preferred_skills: JobIntelligenceSkill[];
  required_experience: JobIntelligenceExperience[];
  preferred_experience: JobIntelligenceExperience[];
  education: JobIntelligenceEducation[];
  certifications: JobIntelligenceCertification[];
  responsibilities: JobIntelligenceResponsibility[];
  authorization: {
    sponsorship: string;
    citizenship: string;
    clearance: string;
    work_authorization: string;
  };
  compensation: {
    salary_min: number | null;
    salary_max: number | null;
    currency: string | null;
    period: string;
    evidence_text: string | null;
  };
  domain: {
    value: string | null;
    confidence: string | null;
  };
};

export type JobIntelligenceResponse = {
  id: string;
  job_id: string;
  analysis_version: string;
  extraction_status: string;
  created_at: string;
  intelligence: JobIntelligenceData;
};

export type EligibilityStatus = "eligible" | "ineligible" | "unknown";

export type EligibilityCheckStatus = "pass" | "fail" | "unknown" | "not_applicable";

export type EligibilityCheck = {
  constraint: string;
  status: EligibilityCheckStatus;
  reason: string;
};

export type JobEligibilityResult = {
  id: string;
  job_id: string;
  status: EligibilityStatus;
  engine_version: string;
  checks: EligibilityCheck[];
  failed_constraints: string[];
  unknown_constraints: string[];
  reasons: string[];
  evaluated_at: string;
};

function authHeaders(): Record<string, string> {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("ai_job_intelligence_token")
      : null;

  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function getJobIntelligence(
  jobId: string,
): Promise<JobIntelligenceResponse> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/intelligence`, {
    headers: authHeaders(),
    cache: "no-store",
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : "Unable to load Job Intelligence.";

    throw new Error(message);
  }

  return data as JobIntelligenceResponse;
}

export async function generateJobIntelligence(
  jobId: string,
): Promise<JobIntelligenceResponse> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/intelligence`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    cache: "no-store",
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : "Unable to generate Job Intelligence.";

    throw new Error(message);
  }

  return data as JobIntelligenceResponse;
}

export async function getJobEligibility(
  jobId: string,
): Promise<JobEligibilityResult> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/eligibility`, {
    headers: authHeaders(),
    cache: "no-store",
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : "Unable to check eligibility.";

    throw new Error(message);
  }

  return data as JobEligibilityResult;
}

export type AtsAlignmentStatus = "matched" | "partial" | "missing";

export type AtsRequirementCategory = "must_have" | "preferred";

export type AtsRequirementResult = {
  requirement_id: string;
  requirement_type: "skill" | "experience" | "education" | "certification";
  category: AtsRequirementCategory;
  requirement_text: string;
  status: AtsAlignmentStatus;
  jd_evidence: string;
  resume_evidence: string | null;
  explanation: string;
  confidence: "high" | "medium" | "low";
};

export type AtsScoreComponent = {
  name: string;
  weight: number;
  score: number;
  weighted_score: number;
  explanation: string;
};

export type AtsAlignmentResult = {
  id: string;
  job_id: string;
  resume_version_id: string;
  job_intelligence_id: string;
  engine_version: string;
  overall_score: number;
  confidence: "high" | "medium" | "low";
  scoring_version: string;
  must_have_total: number;
  must_have_matched: number;
  preferred_total: number;
  preferred_matched: number;
  must_have_ceiling: number | null;
  score_components: AtsScoreComponent[];
  requirement_results: AtsRequirementResult[];
  created_at: string;
};

// resumeVersionId is optional: when omitted, the query param is left off
// entirely and the backend falls back to its existing default resume
// resolution (most recent Resume, preferring its master ResumeVersion) -
// AJI-019 never changes that default, it only lets the caller override it.
export async function calculateAtsAlignment(
  jobId: string,
  resumeVersionId?: string,
): Promise<AtsAlignmentResult> {
  const searchParams = new URLSearchParams();
  if (resumeVersionId) {
    searchParams.set("resume_version_id", resumeVersionId);
  }
  const query = searchParams.toString();

  const response = await fetch(
    `${API_BASE_URL}/jobs/${jobId}/ats${query ? `?${query}` : ""}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      cache: "no-store",
    },
  );

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : "Unable to calculate ATS Alignment.";

    throw new Error(message);
  }

  return data as AtsAlignmentResult;
}

export async function calculateJobMatch(
  jobId: string,
  resumeVersionId?: string,
): Promise<JobMatchResult> {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("ai_job_intelligence_token")
      : null;

  const searchParams = new URLSearchParams();
  if (resumeVersionId) {
    searchParams.set("resume_version_id", resumeVersionId);
  }
  const query = searchParams.toString();

  const response = await fetch(
    `${API_BASE_URL}/jobs/${jobId}/match${query ? `?${query}` : ""}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token
          ? {
              Authorization: `Bearer ${token}`,
            }
          : {}),
      },
      cache: "no-store",
    },
  );

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : "Unable to calculate job match.";

    throw new Error(message);
  }

  return data as JobMatchResult;
}

export type GapSuggestionType =
  | "ADD_IF_TRUE"
  | "REPHRASE_EXISTING"
  | "HIGHLIGHT_EXISTING";

export type GapSuggestion = {
  requirement_id: string;
  requirement_type: "skill" | "experience" | "education" | "certification";
  category: AtsRequirementCategory;
  requirement_text: string;
  status: "partial" | "missing";
  jd_evidence: string;
  resume_evidence: string | null;
  suggestion_type: GapSuggestionType;
  explanation: string;
  explanation_source: "ai" | "deterministic";
  suggestion_text: string;
  suggestion_source: "ai" | "deterministic";
  confidence: "high" | "medium" | "low";
};

export type GapAnalysisResult = {
  id: string;
  job_id: string;
  resume_version_id: string;
  job_intelligence_id: string;
  ats_alignment_id: string;
  analysis_version: string;
  analyzer_version: string;
  prompt_version: string;
  model_provider: string | null;
  model_name: string | null;
  generation_status: string;
  must_have_gap_count: number;
  preferred_gap_count: number;
  gaps: GapSuggestion[];
  created_at: string;
};

export async function getGapAnalysis(
  jobId: string,
  resumeVersionId?: string,
): Promise<GapAnalysisResult> {
  const searchParams = new URLSearchParams();
  if (resumeVersionId) {
    searchParams.set("resume_version_id", resumeVersionId);
  }
  const query = searchParams.toString();

  const response = await fetch(
    `${API_BASE_URL}/jobs/${jobId}/gap-analysis${query ? `?${query}` : ""}`,
    {
      headers: authHeaders(),
      cache: "no-store",
    },
  );

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : "Unable to load Gap Analysis.";

    throw new Error(message);
  }

  return data as GapAnalysisResult;
}

export async function calculateGapAnalysis(
  jobId: string,
  resumeVersionId?: string,
): Promise<GapAnalysisResult> {
  const searchParams = new URLSearchParams();
  if (resumeVersionId) {
    searchParams.set("resume_version_id", resumeVersionId);
  }
  const query = searchParams.toString();

  const response = await fetch(
    `${API_BASE_URL}/jobs/${jobId}/gap-analysis${query ? `?${query}` : ""}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      cache: "no-store",
    },
  );

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : "Unable to calculate Gap Analysis.";

    throw new Error(message);
  }

  return data as GapAnalysisResult;
}

// ---------------------------------------------------------------------------
// Resume Improvement Approval & Recheck (AJI-021)
// ---------------------------------------------------------------------------

export type ImprovementDecisionAction = "approve" | "skip";

/**
 * One submitted decision. There is deliberately no `suggestion_type` or
 * `applied_text` field: the backend reads the suggestion type from the
 * stored Gap Analysis row and writes only `user_content`, and rejects a
 * request carrying either field outright.
 */
export type ImprovementDecisionInput = {
  requirement_id: string;
  action: ImprovementDecisionAction;
  truth_confirmed?: boolean;
  user_content?: string | null;
};

export type ImprovementDecisionRecord = {
  requirement_id: string;
  requirement_text: string;
  category: AtsRequirementCategory;
  suggestion_type: GapSuggestionType;
  action: ImprovementDecisionAction;
  truth_confirmed: boolean;
  applied_text: string | null;
  content_source: "user" | "none";
};

export type RequirementTransitionDirection =
  | "improved"
  | "unchanged"
  | "regressed"
  | "added"
  | "removed";

export type RequirementTransition = {
  requirement_id: string;
  requirement_text: string;
  category: AtsRequirementCategory;
  before_status: AtsAlignmentStatus | null;
  after_status: AtsAlignmentStatus | null;
  direction: RequirementTransitionDirection;
  was_approved: boolean;
};

export type ImprovementComparison = {
  baseline_ats_alignment_id: string;
  baseline_resume_version_id: string;
  baseline_score: number;
  baseline_must_have_matched: number;
  baseline_must_have_total: number;
  baseline_preferred_matched: number;
  baseline_preferred_total: number;
  recheck_ats_alignment_id: string;
  recheck_resume_version_id: string;
  recheck_score: number;
  recheck_must_have_matched: number;
  recheck_must_have_total: number;
  recheck_preferred_matched: number;
  recheck_preferred_total: number;
  score_delta: number;
  must_have_delta: number;
  preferred_delta: number;
  improved_count: number;
  unchanged_count: number;
  regressed_count: number;
  transitions: RequirementTransition[];
};

export type ResumeImprovementResult = {
  id: string;
  job_id: string;
  gap_analysis_id: string;
  baseline_ats_alignment_id: string;
  parent_resume_version_id: string;
  child_resume_version_id: string;
  child_resume_version_name: string;
  engine_version: string;
  approved_count: number;
  skipped_count: number;
  recheck_status: "pending" | "complete" | "failed";
  recheck_error: string | null;
  recheck_ats_alignment_id: string | null;
  decisions: ImprovementDecisionRecord[];
  // null whenever the recheck has not produced a result - the created
  // version is still reported in full, because a failed recheck never
  // costs the user the version they approved.
  comparison: ImprovementComparison | null;
  created_at: string;
  updated_at: string;
};

/**
 * The backend returns `{ code, message }` for this feature's own errors
 * so the UI can distinguish "you still need to confirm this is true"
 * from a transport failure without matching on prose.
 */
export class ResumeImprovementError extends Error {
  code: string;

  constructor(message: string, code: string) {
    super(message);
    this.name = "ResumeImprovementError";
    this.code = code;
  }
}

function toImprovementError(data: unknown, fallback: string): Error {
  const detail = (data as { detail?: unknown } | null)?.detail;

  if (detail && typeof detail === "object" && "message" in detail) {
    const { message, code } = detail as { message?: string; code?: string };
    return new ResumeImprovementError(message || fallback, code || "error");
  }

  if (typeof detail === "string") {
    return new ResumeImprovementError(detail, "error");
  }

  return new ResumeImprovementError(fallback, "error");
}

export async function getResumeImprovement(
  jobId: string,
  resumeVersionId?: string,
): Promise<ResumeImprovementResult> {
  const searchParams = new URLSearchParams();
  if (resumeVersionId) {
    searchParams.set("resume_version_id", resumeVersionId);
  }
  const query = searchParams.toString();

  const response = await fetch(
    `${API_BASE_URL}/jobs/${jobId}/resume-improvement${query ? `?${query}` : ""}`,
    {
      headers: authHeaders(),
      cache: "no-store",
    },
  );

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw toImprovementError(data, "Unable to load your approved improvements.");
  }

  return data as ResumeImprovementResult;
}

export async function createResumeImprovement(
  jobId: string,
  gapAnalysisId: string,
  decisions: ImprovementDecisionInput[],
): Promise<ResumeImprovementResult> {
  const response = await fetch(
    `${API_BASE_URL}/jobs/${jobId}/resume-improvement`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: JSON.stringify({
        gap_analysis_id: gapAnalysisId,
        decisions,
      }),
      cache: "no-store",
    },
  );

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw toImprovementError(
      data,
      "Unable to apply your approved improvements.",
    );
  }

  return data as ResumeImprovementResult;
}

export async function retryResumeImprovementRecheck(
  jobId: string,
  improvementId: string,
): Promise<ResumeImprovementResult> {
  const response = await fetch(
    `${API_BASE_URL}/jobs/${jobId}/resume-improvement/${improvementId}/recheck`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      cache: "no-store",
    },
  );

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw toImprovementError(data, "Unable to recheck your new version.");
  }

  return data as ResumeImprovementResult;
}
