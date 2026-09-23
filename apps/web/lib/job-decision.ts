// AJI-023 — NERO Job Intelligence -> Application Decision Workflow.
//
// A deterministic *presentation* layer over results the existing engines
// already produced. It never scores, ranks or recommends a job: it reads
// Job Intelligence, Hard Eligibility, Job Match, ATS Alignment, Gap
// Analysis, Resume Improvement and the tracking record exactly as the API
// returned them and arranges them into one ordered workflow.
//
// Two rules keep it honest:
//  - Job Match, ATS Alignment and Gap Analysis stay separate. Nothing
//    here combines their numbers; each stage reports only its own result.
//  - Every list (alignment areas, partial/missing requirements, blockers,
//    resume actions) is a filter over verified engine output, never text
//    NERO composed. When a real AI layer arrives it plugs in behind those
//    same engines, and this file keeps working unchanged.

import type { Application } from "./applications";
import type {
  AtsAlignmentResult,
  AtsRequirementResult,
  EligibilityCheck,
  GapAnalysisResult,
  GapSuggestionType,
  JobEligibilityResult,
  JobIntelligenceData,
  JobMatchResult,
  ResumeImprovementResult,
} from "./jobs";

export type ResumeAvailability = "loading" | "error" | "empty" | "ready";

export type StageKey =
  | "intelligence"
  | "eligibility"
  | "match"
  | "ats"
  | "gap"
  | "improvement"
  | "application";

/**
 * - not_started: no result exists yet for this job/resume version.
 * - loading: the request for this stage is in flight.
 * - ready: a verified result is shown.
 * - attention: a result exists but is incomplete or out of date.
 * - blocked: cannot run yet (no resume, or an earlier stage is missing).
 * - error: the last request for this stage failed; it can be retried.
 */
export type StageStatus =
  | "not_started"
  | "loading"
  | "ready"
  | "attention"
  | "blocked"
  | "error";

export type DecisionStage = {
  key: StageKey;
  label: string;
  status: StageStatus;
  /** One line built only from the stage's own result. */
  summary: string;
};

export type NextStepKey =
  | "upload_resume"
  | "analyze_job"
  | "check_eligibility"
  | "calculate_match"
  | "calculate_ats"
  | "analyze_gaps"
  | "review_improvements"
  | "save_job"
  | "mark_applied"
  | "view_application";

export type NextStep = {
  key: NextStepKey;
  label: string;
  description: string;
};

export type ResumeActionSummary = {
  total: number;
  byType: Record<GapSuggestionType, number>;
  improvementCreated: boolean;
};

export type JobDecisionInputs = {
  resume: ResumeAvailability;
  /** Reading this job's previously saved Match/ATS/Gap/Improvement. */
  savedResultsLoading?: boolean;
  intelligence?: JobIntelligenceData;
  intelligenceStatus?: string;
  intelligenceLoading?: boolean;
  intelligenceError?: string;
  eligibility?: JobEligibilityResult;
  eligibilityLoading?: boolean;
  eligibilityError?: string;
  match?: JobMatchResult;
  matchLoading?: boolean;
  matchError?: string;
  ats?: AtsAlignmentResult;
  atsLoading?: boolean;
  atsError?: string;
  gapAnalysis?: GapAnalysisResult;
  gapLoading?: boolean;
  gapError?: string;
  improvement?: ResumeImprovementResult;
  improvementLoading?: boolean;
  improvementError?: string;
  application?: Application;
};

export type JobDecision = {
  characterState: "Idle" | "Analyzing" | "Success";
  stages: DecisionStage[];
  /** ATS requirements the resume demonstrates, must-have first. */
  alignmentAreas: AtsRequirementResult[];
  /** ATS requirements the resume only partly demonstrates. */
  partialRequirements: AtsRequirementResult[];
  /** ATS requirements with no resume evidence, must-have first. */
  missingRequirements: AtsRequirementResult[];
  eligibilityBlockers: EligibilityCheck[];
  eligibilityUnknowns: EligibilityCheck[];
  resumeActions: ResumeActionSummary | null;
  /** True when Match, ATS and Gap were not all computed against the
   *  same ResumeVersion (only checked across results that exist). */
  resumeVersionMismatch: boolean;
  /** True when the Gap Analysis on screen was built from a different
   *  ATS Alignment result than the one on screen. */
  gapBasedOnOtherAts: boolean;
  nextStep: NextStep | null;
};

const RESUME_REQUIRED_SUMMARY = "Upload a resume to calculate.";

function mustHaveFirst(items: AtsRequirementResult[]): AtsRequirementResult[] {
  return [...items].sort((a, b) =>
    a.category === b.category ? 0 : a.category === "must_have" ? -1 : 1,
  );
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

function titleCase(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

const SAVED_RESULTS_LOADING_SUMMARY = "Loading saved result…";

function resumeStageStatus(
  inputs: JobDecisionInputs,
  loading: boolean | undefined,
  error: string | undefined,
  hasResult: boolean,
): StageStatus {
  if (loading) return "loading";
  if (error) return "error";
  if (hasResult) return "ready";
  if (inputs.savedResultsLoading) return "loading";
  if (inputs.resume === "empty") return "blocked";
  return "not_started";
}

export function buildJobDecision(inputs: JobDecisionInputs): JobDecision {
  const {
    intelligence,
    eligibility,
    match,
    ats,
    gapAnalysis,
    improvement,
    application,
  } = inputs;

  const noResume = inputs.resume === "empty";

  // --- Job Intelligence ---------------------------------------------------
  let intelligenceStage: DecisionStage;
  if (inputs.intelligenceLoading) {
    intelligenceStage = {
      key: "intelligence",
      label: "Job Intelligence",
      status: "loading",
      summary: "Reading this job description…",
    };
  } else if (inputs.intelligenceError) {
    intelligenceStage = {
      key: "intelligence",
      label: "Job Intelligence",
      status: "error",
      summary: inputs.intelligenceError,
    };
  } else if (intelligence) {
    const counts = `${plural(
      intelligence.required_skills.length,
      "required skill",
      "required skills",
    )} · ${intelligence.preferred_skills.length} preferred`;
    const partial = inputs.intelligenceStatus === "partial";
    intelligenceStage = {
      key: "intelligence",
      label: "Job Intelligence",
      status: partial ? "attention" : "ready",
      summary: partial
        ? `${counts} · deterministic extraction only`
        : counts,
    };
  } else {
    intelligenceStage = {
      key: "intelligence",
      label: "Job Intelligence",
      status: "not_started",
      summary: "Not analyzed yet.",
    };
  }

  // --- Hard Eligibility ----------------------------------------------------
  const eligibilityBlockers =
    eligibility?.checks.filter((check) => check.status === "fail") ?? [];
  const eligibilityUnknowns =
    eligibility?.checks.filter((check) => check.status === "unknown") ?? [];

  const eligibilityStage: DecisionStage = {
    key: "eligibility",
    label: "Hard Eligibility",
    status: inputs.eligibilityLoading
      ? "loading"
      : inputs.eligibilityError
        ? "error"
        : eligibility
          ? eligibility.status === "eligible"
            ? "ready"
            : "attention"
          : "not_started",
    summary: inputs.eligibilityLoading
      ? "Checking your hard requirements…"
      : inputs.eligibilityError
        ? inputs.eligibilityError
        : eligibility
          ? eligibility.status === "ineligible"
            ? `Ineligible · ${plural(eligibilityBlockers.length, "blocker", "blockers")}`
            : eligibility.status === "unknown"
              ? `Unknown · ${plural(eligibilityUnknowns.length, "unverified check", "unverified checks")}`
              : "Eligible · no configured requirement rules this job out"
          : "Not checked yet.",
  };

  // --- Job Match -----------------------------------------------------------
  const matchStatus = resumeStageStatus(
    inputs,
    inputs.matchLoading,
    inputs.matchError,
    Boolean(match),
  );
  const matchStage: DecisionStage = {
    key: "match",
    label: "Job Match",
    status: matchStatus,
    summary:
      matchStatus === "loading"
        ? inputs.matchLoading
          ? "Calculating…"
          : SAVED_RESULTS_LOADING_SUMMARY
        : matchStatus === "error"
          ? (inputs.matchError as string)
          : match
            ? `${Math.round(match.score)}% · ${match.confidence} confidence`
            : noResume
              ? RESUME_REQUIRED_SUMMARY
              : "Not calculated yet.",
  };

  // --- ATS Alignment -------------------------------------------------------
  const atsStatus = resumeStageStatus(
    inputs,
    inputs.atsLoading,
    inputs.atsError,
    Boolean(ats),
  );
  const atsStage: DecisionStage = {
    key: "ats",
    label: "ATS Alignment",
    status: atsStatus,
    summary:
      atsStatus === "loading"
        ? inputs.atsLoading
          ? "Analyzing…"
          : SAVED_RESULTS_LOADING_SUMMARY
        : atsStatus === "error"
          ? (inputs.atsError as string)
          : ats
            ? `${Math.round(ats.overall_score)}% · must-have ${ats.must_have_matched}/${ats.must_have_total}`
            : noResume
              ? RESUME_REQUIRED_SUMMARY
              : "Not calculated yet.",
  };

  // --- Gap Analysis --------------------------------------------------------
  const gapBasedOnOtherAts = Boolean(
    gapAnalysis && ats && gapAnalysis.ats_alignment_id !== ats.id,
  );
  let gapStatus = resumeStageStatus(
    inputs,
    inputs.gapLoading,
    inputs.gapError,
    Boolean(gapAnalysis),
  );
  if (gapStatus === "ready" && gapBasedOnOtherAts) {
    gapStatus = "attention";
  }
  const gapCount = gapAnalysis?.gaps.length ?? 0;
  const gapStage: DecisionStage = {
    key: "gap",
    label: "Gap Analysis",
    status: gapStatus,
    summary:
      gapStatus === "loading"
        ? inputs.gapLoading
          ? "Analyzing…"
          : SAVED_RESULTS_LOADING_SUMMARY
        : gapStatus === "error"
          ? (inputs.gapError as string)
          : gapAnalysis
            ? `${plural(gapCount, "gap", "gaps")} · ${gapAnalysis.must_have_gap_count} must-have${
                gapBasedOnOtherAts
                  ? " · built from an earlier ATS result"
                  : ""
              }`
            : noResume
              ? RESUME_REQUIRED_SUMMARY
              : "Not analyzed yet.",
  };

  // --- Resume Improvement --------------------------------------------------
  let resumeActions: ResumeActionSummary | null = null;
  if (gapAnalysis) {
    const byType: Record<GapSuggestionType, number> = {
      ADD_IF_TRUE: 0,
      REPHRASE_EXISTING: 0,
      HIGHLIGHT_EXISTING: 0,
    };
    for (const gap of gapAnalysis.gaps) {
      if (gap.suggestion_type in byType) {
        byType[gap.suggestion_type] += 1;
      }
    }
    resumeActions = {
      total: gapAnalysis.gaps.length,
      byType,
      improvementCreated: Boolean(improvement),
    };
  }

  let improvementStage: DecisionStage;
  if (inputs.improvementLoading) {
    improvementStage = {
      key: "improvement",
      label: "Resume Improvement",
      status: "loading",
      summary: "Working on your approved improvements…",
    };
  } else if (inputs.improvementError) {
    improvementStage = {
      key: "improvement",
      label: "Resume Improvement",
      status: "error",
      summary: inputs.improvementError,
    };
  } else if (improvement) {
    const recheck =
      improvement.recheck_status === "complete" && improvement.comparison
        ? `recheck ${improvement.comparison.score_delta >= 0 ? "+" : ""}${Math.round(
            improvement.comparison.score_delta,
          )} ATS`
        : improvement.recheck_status === "failed"
          ? "recheck failed"
          : "recheck pending";
    improvementStage = {
      key: "improvement",
      label: "Resume Improvement",
      status: improvement.recheck_status === "complete" ? "ready" : "attention",
      summary: `${improvement.child_resume_version_name} created · ${recheck}`,
    };
  } else if (gapAnalysis) {
    improvementStage = {
      key: "improvement",
      label: "Resume Improvement",
      status: gapCount > 0 ? "not_started" : "ready",
      summary:
        gapCount > 0
          ? `${plural(gapCount, "suggestion", "suggestions")} available to review`
          : "No improvements needed for this resume.",
    };
  } else {
    improvementStage = {
      key: "improvement",
      label: "Resume Improvement",
      status: "blocked",
      summary: noResume
        ? RESUME_REQUIRED_SUMMARY
        : "Available after Gap Analysis.",
    };
  }

  // --- Application ---------------------------------------------------------
  const applicationStage: DecisionStage = {
    key: "application",
    label: "Application Tracking",
    status: application ? "ready" : "not_started",
    summary: application
      ? `${titleCase(application.status)}${
          application.status === "saved" ? " · not applied yet" : ""
        }`
      : "Not tracked yet.",
  };

  // --- Cross-artifact consistency (display only, never merged) ------------
  const versionIds = new Set(
    [match, ats, gapAnalysis]
      .filter((result): result is NonNullable<typeof result> => Boolean(result))
      .map((result) => result.resume_version_id),
  );

  // --- Requirement lists from the ATS result only --------------------------
  const requirements = ats?.requirement_results ?? [];

  const stages = [
    intelligenceStage,
    eligibilityStage,
    matchStage,
    atsStage,
    gapStage,
    improvementStage,
    applicationStage,
  ];

  const anyLoading = stages.some((stage) => stage.status === "loading");
  const coreComplete = Boolean(intelligence && match && ats && gapAnalysis);

  return {
    characterState: anyLoading ? "Analyzing" : coreComplete ? "Success" : "Idle",
    stages,
    alignmentAreas: mustHaveFirst(
      requirements.filter((item) => item.status === "matched"),
    ),
    partialRequirements: mustHaveFirst(
      requirements.filter((item) => item.status === "partial"),
    ),
    missingRequirements: mustHaveFirst(
      requirements.filter((item) => item.status === "missing"),
    ),
    eligibilityBlockers,
    eligibilityUnknowns,
    resumeActions,
    resumeVersionMismatch: versionIds.size > 1,
    gapBasedOnOtherAts,
    nextStep: nextStepFor(inputs, gapCount),
  };
}

/**
 * The first workflow stage that has not produced a result yet. This is
 * workflow navigation (what hasn't been run), never a judgement about
 * whether to apply — that decision is always the user's.
 */
function nextStepFor(
  inputs: JobDecisionInputs,
  gapCount: number,
): NextStep | null {
  const anyLoading =
    inputs.savedResultsLoading ||
    inputs.intelligenceLoading ||
    inputs.eligibilityLoading ||
    inputs.matchLoading ||
    inputs.atsLoading ||
    inputs.gapLoading ||
    inputs.improvementLoading;

  if (anyLoading) return null;

  if (!inputs.intelligence) {
    return {
      key: "analyze_job",
      label: "Analyze this job",
      description: "Extract the job's requirements before anything else.",
    };
  }

  if (!inputs.eligibility) {
    return {
      key: "check_eligibility",
      label: "Check eligibility",
      description: "Compare the job against your hard requirements.",
    };
  }

  // Wait for the resume list rather than skip past the resume stages.
  if (inputs.resume === "loading") return null;

  if (inputs.resume === "empty") {
    return {
      key: "upload_resume",
      label: "Upload a resume",
      description:
        "Job Match, ATS Alignment and Gap Analysis all need a resume.",
    };
  }

  if (inputs.resume === "ready") {
    if (!inputs.match) {
      return {
        key: "calculate_match",
        label: "Calculate Job Match",
        description: "See how this job fits you overall.",
      };
    }

    if (!inputs.ats) {
      return {
        key: "calculate_ats",
        label: "Calculate ATS Alignment",
        description: "See how your resume reads against this job description.",
      };
    }

    if (!inputs.gapAnalysis) {
      return {
        key: "analyze_gaps",
        label: "Analyze gaps",
        description: "List the requirements your resume doesn't clearly show.",
      };
    }

    if (gapCount > 0 && !inputs.improvement) {
      return {
        key: "review_improvements",
        label: "Review resume improvements",
        description:
          "Approve only the suggestions that are true for you. Nothing changes without your approval.",
      };
    }
  }

  if (!inputs.application) {
    return {
      key: "save_job",
      label: "Save to Application Tracking",
      description: "Keep this job in your pipeline. NERO never applies for you.",
    };
  }

  if (inputs.application.status === "saved") {
    return {
      key: "mark_applied",
      label: "Mark as applied",
      description:
        "Record it here once you've applied on the employer's site. NERO never submits applications.",
    };
  }

  return {
    key: "view_application",
    label: "View application",
    description: "Update the status as you hear back.",
  };
}
