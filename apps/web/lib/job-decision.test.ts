// AJI-023 — the deterministic decision layer: stages, lists and the next
// workflow step are derived only from existing engine output.
import { describe, expect, it } from "vitest";
import type { Application } from "./applications";
import { buildJobDecision, type JobDecisionInputs } from "./job-decision";
import type {
  AtsAlignmentResult,
  AtsRequirementResult,
  GapAnalysisResult,
  JobEligibilityResult,
  JobIntelligenceData,
  JobMatchResult,
  ResumeImprovementResult,
} from "./jobs";

const INTELLIGENCE = {
  required_skills: [
    { canonical_skill: "Python", level: "required", evidence_text: "Python", confidence: "high" },
    { canonical_skill: "SQL", level: "required", evidence_text: "SQL", confidence: "high" },
  ],
  preferred_skills: [
    { canonical_skill: "AWS", level: "preferred", evidence_text: "AWS", confidence: "medium" },
  ],
} as unknown as JobIntelligenceData;

const ELIGIBLE = {
  status: "eligible",
  checks: [{ constraint: "location", status: "pass", reason: "ok" }],
} as unknown as JobEligibilityResult;

const INELIGIBLE = {
  status: "ineligible",
  checks: [
    { constraint: "employment_type", status: "fail", reason: "Contract only" },
    { constraint: "work_authorization", status: "unknown", reason: "Not stated" },
  ],
} as unknown as JobEligibilityResult;

function requirement(
  id: string,
  category: "must_have" | "preferred",
  status: "matched" | "partial" | "missing",
): AtsRequirementResult {
  return {
    requirement_id: id,
    requirement_type: "skill",
    category,
    requirement_text: id,
    status,
    jd_evidence: id,
    resume_evidence: null,
    explanation: "",
    confidence: "high",
  };
}

const MATCH = {
  id: "match-1",
  resume_version_id: "rv-1",
  score: 71.6,
  confidence: "medium",
} as unknown as JobMatchResult;

const ATS = {
  id: "ats-1",
  resume_version_id: "rv-1",
  overall_score: 58.2,
  must_have_matched: 1,
  must_have_total: 3,
  requirement_results: [
    requirement("aws", "preferred", "matched"),
    requirement("python", "must_have", "matched"),
    requirement("kafka", "preferred", "missing"),
    requirement("sql", "must_have", "partial"),
    requirement("go", "must_have", "missing"),
  ],
} as unknown as AtsAlignmentResult;

const GAP = {
  id: "gap-1",
  resume_version_id: "rv-1",
  ats_alignment_id: "ats-1",
  must_have_gap_count: 2,
  gaps: [
    { requirement_id: "sql", suggestion_type: "REPHRASE_EXISTING" },
    { requirement_id: "go", suggestion_type: "ADD_IF_TRUE" },
    { requirement_id: "kafka", suggestion_type: "ADD_IF_TRUE" },
  ],
} as unknown as GapAnalysisResult;

const IMPROVEMENT = {
  gap_analysis_id: "gap-1",
  child_resume_version_name: "Resume v2",
  recheck_status: "complete",
  comparison: { score_delta: 6.4 },
} as unknown as ResumeImprovementResult;

function application(status: Application["status"]): Application {
  return { id: "app-1", status } as Application;
}

const COMPLETE: JobDecisionInputs = {
  resume: "ready",
  intelligence: INTELLIGENCE,
  intelligenceStatus: "complete",
  eligibility: ELIGIBLE,
  match: MATCH,
  ats: ATS,
  gapAnalysis: GAP,
};

function stage(inputs: JobDecisionInputs, key: string) {
  return buildJobDecision(inputs).stages.find((item) => item.key === key)!;
}

describe("buildJobDecision", () => {
  it("orders the workflow from Job Intelligence to Application Tracking", () => {
    expect(buildJobDecision({ resume: "ready" }).stages.map((s) => s.key)).toEqual([
      "intelligence",
      "eligibility",
      "match",
      "ats",
      "gap",
      "improvement",
      "application",
    ]);
  });

  it("starts idle with nothing run and the job analysis as the next step", () => {
    const decision = buildJobDecision({ resume: "ready" });

    expect(decision.characterState).toBe("Idle");
    expect(decision.stages.every((s) => s.status !== "ready")).toBe(true);
    expect(decision.nextStep?.key).toBe("analyze_job");
    expect(decision.alignmentAreas).toEqual([]);
    expect(decision.resumeActions).toBeNull();
  });

  it("blocks the resume-based stages and asks for a resume when there is none", () => {
    const inputs: JobDecisionInputs = {
      resume: "empty",
      intelligence: INTELLIGENCE,
      eligibility: ELIGIBLE,
    };
    const decision = buildJobDecision(inputs);

    for (const key of ["match", "ats", "gap", "improvement"]) {
      const item = stage(inputs, key);
      expect(item.status).toBe("blocked");
      expect(item.summary).toBe("Upload a resume to calculate.");
    }
    expect(decision.nextStep?.key).toBe("upload_resume");
  });

  it("marks deterministic-only Job Intelligence as needing review, never complete", () => {
    const item = stage(
      { resume: "ready", intelligence: INTELLIGENCE, intelligenceStatus: "partial" },
      "intelligence",
    );

    expect(item.status).toBe("attention");
    expect(item.summary).toBe(
      "2 required skills · 1 preferred · deterministic extraction only",
    );
  });

  it("reports each score only on its own stage, never combined", () => {
    const decision = buildJobDecision(COMPLETE);

    expect(stage(COMPLETE, "match").summary).toBe("72% · medium confidence");
    expect(stage(COMPLETE, "ats").summary).toBe("58% · must-have 1/3");
    expect(stage(COMPLETE, "gap").summary).toBe("3 gaps · 2 must-have");
    // No stage mentions another stage's number.
    expect(stage(COMPLETE, "match").summary).not.toContain("58");
    expect(stage(COMPLETE, "ats").summary).not.toContain("72");
    expect(decision.characterState).toBe("Success");
  });

  it("splits ATS requirements into aligned / partial / missing, must-have first", () => {
    const decision = buildJobDecision(COMPLETE);

    expect(decision.alignmentAreas.map((r) => r.requirement_id)).toEqual([
      "python",
      "aws",
    ]);
    expect(decision.partialRequirements.map((r) => r.requirement_id)).toEqual([
      "sql",
    ]);
    expect(decision.missingRequirements.map((r) => r.requirement_id)).toEqual([
      "go",
      "kafka",
    ]);
  });

  it("counts the available resume actions from the Gap Analysis", () => {
    const decision = buildJobDecision(COMPLETE);

    expect(decision.resumeActions).toEqual({
      total: 3,
      byType: { ADD_IF_TRUE: 2, REPHRASE_EXISTING: 1, HIGHLIGHT_EXISTING: 0 },
      improvementCreated: false,
    });
    expect(stage(COMPLETE, "improvement").summary).toBe(
      "3 suggestions available to review",
    );
    expect(decision.nextStep?.key).toBe("review_improvements");
  });

  it("summarizes a created improvement and its recheck", () => {
    const inputs = { ...COMPLETE, improvement: IMPROVEMENT };

    expect(stage(inputs, "improvement")).toMatchObject({
      status: "ready",
      summary: "Resume v2 created · recheck +6 ATS",
    });
    expect(buildJobDecision(inputs).nextStep?.key).toBe("save_job");
  });

  it("surfaces eligibility blockers and unknown checks verbatim", () => {
    const decision = buildJobDecision({ ...COMPLETE, eligibility: INELIGIBLE });

    expect(decision.eligibilityBlockers.map((c) => c.reason)).toEqual([
      "Contract only",
    ]);
    expect(decision.eligibilityUnknowns.map((c) => c.reason)).toEqual([
      "Not stated",
    ]);
    expect(stage({ ...COMPLETE, eligibility: INELIGIBLE }, "eligibility")).toMatchObject({
      status: "attention",
      summary: "Ineligible · 1 blocker",
    });
  });

  it("flags a Gap Analysis built from a different ATS result", () => {
    const inputs = {
      ...COMPLETE,
      gapAnalysis: { ...GAP, ats_alignment_id: "ats-old" },
    };
    const decision = buildJobDecision(inputs);

    expect(decision.gapBasedOnOtherAts).toBe(true);
    expect(stage(inputs, "gap").status).toBe("attention");
  });

  it("flags results calculated for different resume versions", () => {
    const decision = buildJobDecision({
      ...COMPLETE,
      match: { ...MATCH, resume_version_id: "rv-2" },
    });

    expect(decision.resumeVersionMismatch).toBe(true);
    expect(buildJobDecision(COMPLETE).resumeVersionMismatch).toBe(false);
  });

  it("shows loading and errors per stage, with retry available on errors", () => {
    const loading = buildJobDecision({ ...COMPLETE, ats: undefined, atsLoading: true });
    expect(loading.characterState).toBe("Analyzing");
    expect(loading.nextStep).toBeNull();

    const failed = { ...COMPLETE, ats: undefined, atsError: "Service unavailable" };
    expect(stage(failed, "ats")).toMatchObject({
      status: "error",
      summary: "Service unavailable",
    });
  });

  it("shows saved results as loading instead of not-run while they are read", () => {
    const inputs: JobDecisionInputs = {
      resume: "ready",
      intelligence: INTELLIGENCE,
      savedResultsLoading: true,
    };

    expect(stage(inputs, "match")).toMatchObject({
      status: "loading",
      summary: "Loading saved result…",
    });
    expect(buildJobDecision(inputs).nextStep).toBeNull();
  });

  it("moves through Save → Mark Applied → View application, never applying itself", () => {
    const done = { ...COMPLETE, improvement: IMPROVEMENT };

    expect(buildJobDecision(done).nextStep?.key).toBe("save_job");
    expect(
      buildJobDecision({ ...done, application: application("saved") }).nextStep?.key,
    ).toBe("mark_applied");
    expect(
      buildJobDecision({ ...done, application: application("applied") }).nextStep?.key,
    ).toBe("view_application");
    expect(stage({ ...done, application: application("saved") }, "application").summary).toBe(
      "Saved · not applied yet",
    );
  });
});
