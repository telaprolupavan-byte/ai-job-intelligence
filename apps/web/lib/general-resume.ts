import { API_URL } from "./api";
import { getAuthToken } from "./auth";

// AJI-027 — General Resume Intelligence. Job-independent: none of these
// calls takes a job, and the General Resume Score is not an ATS score.

export type ComponentKey =
  | "structure"
  | "action_writing"
  | "measurable_impact"
  | "clarity"
  | "skill_evidence";

export type ScoreComponent = {
  key: ComponentKey;
  label: string;
  status: "scored" | "insufficient_data";
  score: number | null;
  weight: number;
  numerator: number;
  denominator: number;
  detail: string;
};

export type SuggestionType = "REPHRASE_EXISTING" | "ADD_IF_TRUE" | "ADVISORY";

export type GeneralImprovement = {
  improvement_id: string;
  kind: string;
  suggestion_type: SuggestionType;
  components: ComponentKey[];
  issues: string[];
  title: string;
  evidence: string | null;
  target: string | null;
  explanation: string;
  explanation_source: "ai" | "deterministic";
  guidance: string;
  guidance_source: "ai" | "deterministic";
  // "dismissed" = rejected on this version or an earlier one while the
  // same issue remains.
  status: "open" | "dismissed";
};

// Readiness of the version being viewed, from its own assessment only.
// A refined (child) version never changes its parent's readiness; the
// child and its recheck status are on `latest_review` instead.
export type ReadinessState =
  | "not_assessed"
  | "not_valid"
  | "needs_review"
  | "ready";

export type Readiness = {
  state: ReadinessState;
  open_count: number;
  dismissed_count: number;
};

export type ComponentDelta = {
  key: ComponentKey;
  label: string;
  before: number | null;
  after: number | null;
  delta: number | null;
};

export type ImprovementChange = {
  improvement_id: string;
  title: string;
  transition: "resolved" | "still_present" | "new";
  was_approved: boolean;
  was_rejected: boolean;
};

export type AssessmentComparison = {
  baseline_assessment_id: string;
  baseline_resume_version_id: string;
  baseline_score: number;
  recheck_assessment_id: string;
  recheck_resume_version_id: string;
  recheck_score: number;
  score_delta: number;
  components: ComponentDelta[];
  resolved_count: number;
  still_present_count: number;
  new_count: number;
  changes: ImprovementChange[];
};

export type GeneralReview = {
  id: string;
  assessment_id: string;
  parent_resume_version_id: string;
  parent_resume_version_name: string | null;
  child_resume_version_id: string | null;
  child_resume_version_name: string | null;
  approved_count: number;
  rejected_count: number;
  recheck_status: "not_required" | "pending" | "complete" | "failed";
  recheck_error: string | null;
  comparison: AssessmentComparison | null;
  resulting_readiness: Readiness | null;
  created_at: string;
};

export type GeneralAssessment = {
  id: string;
  resume_version_id: string;
  resume_version_name: string;
  generation_status: "complete" | "partial";
  overall_score: number;
  components: ScoreComponent[];
  improvements: GeneralImprovement[];
  validation: {
    valid: boolean;
    warnings: string[];
    word_count: number;
    section_matches: string[];
  };
  readiness: Readiness;
  latest_review: GeneralReview | null;
  created_at: string;
};

export type ReviewDecisionInput = {
  improvement_id: string;
  action: "approve" | "reject";
  truth_confirmed?: boolean;
  user_content?: string;
};

/** `{ code, message }` errors, so the UI can branch without matching prose. */
export class GeneralResumeError extends Error {
  code: string;
  status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "GeneralResumeError";
    this.code = code;
    this.status = status;
  }
}

// Assessing and rechecking can include one bounded (60s) AI call for
// explanations; this ceiling only guarantees a loading state clears.
const REQUEST_TIMEOUT_MS = 150_000;

async function request<T>(
  path: string,
  fallback: string,
  init: RequestInit = {},
): Promise<T> {
  const token = getAuthToken();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response: Response;

  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      cache: "no-store",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch {
    throw new GeneralResumeError(
      controller.signal.aborted
        ? "The request took too long to respond. Please try again."
        : fallback,
      "network_error",
      0,
    );
  } finally {
    clearTimeout(timer);
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const detail = (data as { detail?: unknown } | null)?.detail;

    if (detail && typeof detail === "object" && "message" in detail) {
      const { message, code } = detail as { message?: string; code?: string };
      throw new GeneralResumeError(
        message || fallback,
        code || "error",
        response.status,
      );
    }

    throw new GeneralResumeError(
      typeof detail === "string" ? detail : fallback,
      "error",
      response.status,
    );
  }

  return data as T;
}

function base(versionId: string): string {
  return `/resumes/versions/${encodeURIComponent(versionId)}/general-assessment`;
}

/** The saved assessment, or null if this version has not been assessed. */
export async function getGeneralAssessment(
  versionId: string,
): Promise<GeneralAssessment | null> {
  try {
    return await request<GeneralAssessment>(
      base(versionId),
      "Unable to load the General Resume Score.",
    );
  } catch (err) {
    if (
      err instanceof GeneralResumeError &&
      err.code === "assessment_not_found"
    ) {
      return null;
    }

    throw err;
  }
}

export function createGeneralAssessment(
  versionId: string,
): Promise<GeneralAssessment> {
  return request<GeneralAssessment>(
    base(versionId),
    "Unable to calculate the General Resume Score.",
    { method: "POST" },
  );
}

export function submitGeneralReview(
  versionId: string,
  assessmentId: string,
  decisions: ReviewDecisionInput[],
): Promise<GeneralReview> {
  return request<GeneralReview>(
    `${base(versionId)}/${encodeURIComponent(assessmentId)}/review`,
    "Unable to save your review.",
    { method: "POST", body: JSON.stringify({ decisions }) },
  );
}

export function retryGeneralRecheck(reviewId: string): Promise<GeneralReview> {
  return request<GeneralReview>(
    `/resumes/general-reviews/${encodeURIComponent(reviewId)}/recheck`,
    "Unable to recheck your new version.",
    { method: "POST" },
  );
}
