// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

import type {
  GeneralAssessment,
  GeneralImprovement,
  GeneralReview,
} from "@/lib/general-resume";

vi.mock("@/lib/general-resume", () => ({
  getGeneralAssessment: vi.fn(),
  createGeneralAssessment: vi.fn(),
  submitGeneralReview: vi.fn(),
  retryGeneralRecheck: vi.fn(),
}));

import * as api from "@/lib/general-resume";
import GeneralResumeSection from "./general-resume-section";

const mocked = vi.mocked(api);

function makeImprovement(overrides: Partial<GeneralImprovement> = {}): GeneralImprovement {
  return {
    improvement_id: "imp-bullet",
    kind: "bullet",
    suggestion_type: "REPHRASE_EXISTING",
    components: ["clarity"],
    issues: ["weak_phrase"],
    title: "Bullet with weak phrasing",
    evidence: "Responsible for the data quality checks.",
    target: null,
    explanation: "This bullet uses weak phrasing.",
    explanation_source: "deterministic",
    guidance: "Rewrite this bullet in your own words.",
    guidance_source: "deterministic",
    status: "open",
    ...overrides,
  };
}

function makeAssessment(overrides: Partial<GeneralAssessment> = {}): GeneralAssessment {
  return {
    id: "assessment-1",
    resume_version_id: "version-1",
    resume_version_name: "Original",
    generation_status: "complete",
    overall_score: 72.5,
    components: [
      { key: "structure", label: "Structure & parseability", status: "scored", score: 100, weight: 0.25, numerator: 7, denominator: 7, detail: "7 of 7 structure checks passed." },
      { key: "action_writing", label: "Action-oriented writing", status: "scored", score: 50, weight: 0.25, numerator: 2, denominator: 4, detail: "2 of 4 bullets start with an action verb." },
      { key: "measurable_impact", label: "Measurable impact", status: "scored", score: 50, weight: 0.25, numerator: 2, denominator: 4, detail: "" },
      { key: "clarity", label: "Clarity", status: "scored", score: 90, weight: 0.25, numerator: 9, denominator: 10, detail: "" },
      { key: "skill_evidence", label: "Skill evidence", status: "insufficient_data", score: null, weight: 0, numerator: 0, denominator: 0, detail: "No recognized skills were detected to measure." },
    ],
    improvements: [
      makeImprovement(),
      makeImprovement({
        improvement_id: "imp-metric",
        suggestion_type: "ADD_IF_TRUE",
        title: "Bullet with no measurable result",
        evidence: "Built dashboards for the analytics team.",
      }),
      makeImprovement({
        improvement_id: "imp-advisory",
        kind: "inconsistent_headings",
        suggestion_type: "ADVISORY",
        title: "Inconsistent heading capitalization",
        evidence: null,
      }),
    ],
    validation: { valid: true, warnings: [], word_count: 300, section_matches: [] },
    readiness: { state: "needs_review", open_count: 3, dismissed_count: 0 },
    latest_review: null,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function makeReview(overrides: Partial<GeneralReview> = {}): GeneralReview {
  return {
    id: "review-1",
    assessment_id: "assessment-1",
    parent_resume_version_id: "version-1",
    parent_resume_version_name: "Original",
    child_resume_version_id: "version-2",
    child_resume_version_name: "Refined 1",
    approved_count: 1,
    rejected_count: 2,
    recheck_status: "complete",
    recheck_error: null,
    comparison: {
      baseline_assessment_id: "assessment-1",
      baseline_resume_version_id: "version-1",
      baseline_score: 72.5,
      recheck_assessment_id: "assessment-2",
      recheck_resume_version_id: "version-2",
      recheck_score: 80,
      score_delta: 7.5,
      components: [
        { key: "clarity", label: "Clarity", before: 90, after: 100, delta: 10 },
      ],
      resolved_count: 1,
      still_present_count: 2,
      new_count: 0,
      changes: [],
    },
    resulting_readiness: { state: "ready", open_count: 0, dismissed_count: 2 },
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function renderSection(onOpenVersion = vi.fn()) {
  render(<GeneralResumeSection versionId="version-1" onOpenVersion={onOpenVersion} />);
  return onOpenVersion;
}

function improvementCard(title: string) {
  return screen
    .getAllByTestId("improvement")
    .find((card) => within(card).queryByText(title)) as HTMLElement;
}

beforeEach(() => {
  vi.resetAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("GeneralResumeSection", () => {
  it("states that the score is general, not job-specific and not an ATS score", async () => {
    mocked.getGeneralAssessment.mockResolvedValue(makeAssessment());
    renderSection();

    expect(await screen.findByTestId("general-score")).toHaveTextContent("72.5");
    expect(screen.getByText(/Not specific to any job, and\s+not an ATS score/)).toBeInTheDocument();
    expect(screen.queryByText(/80%/)).not.toBeInTheDocument();
    expect(screen.queryByText(/ATS score:/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/\bpass\b|\bfail\b/i)).not.toBeInTheDocument();
  });

  it("offers to score an unassessed version", async () => {
    mocked.getGeneralAssessment.mockResolvedValue(null);
    mocked.createGeneralAssessment.mockResolvedValue(makeAssessment());
    renderSection();

    fireEvent.click(await screen.findByRole("button", { name: "Get General Resume Score" }));

    expect(await screen.findByTestId("general-score")).toBeInTheDocument();
    expect(mocked.createGeneralAssessment).toHaveBeenCalledWith("version-1");
  });

  it("shows a load error with retry", async () => {
    mocked.getGeneralAssessment.mockRejectedValue(new Error("Unable to load."));
    renderSection();

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to load.");
  });

  it("shows components, including insufficient data, and the partial-AI note", async () => {
    mocked.getGeneralAssessment.mockResolvedValue(
      makeAssessment({ generation_status: "partial" }),
    );
    renderSection();

    expect(await screen.findByText("Not enough data")).toBeInTheDocument();
    expect(screen.getByText("7 of 7 structure checks passed.")).toBeInTheDocument();
    expect(screen.getByTestId("partial-note")).toHaveTextContent(/score and readiness are not affected/);
  });

  it("never pre-fills resume text and requires the user's own wording", async () => {
    mocked.getGeneralAssessment.mockResolvedValue(makeAssessment());
    renderSection();

    await screen.findByTestId("general-score");
    const card = improvementCard("Bullet with weak phrasing");
    fireEvent.click(within(card).getByRole("button", { name: "Approve" }));

    const box = within(card).getByRole("textbox");
    expect(box).toHaveValue("");
    expect(within(card).getByText("Write the text you want in your resume.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create new version and recheck" })).toBeDisabled();

    fireEvent.change(box, { target: { value: "Owned the data quality checks." } });
    expect(screen.getByRole("button", { name: "Create new version and recheck" })).toBeEnabled();
  });

  it("requires truth confirmation for Add-only-if-true items", async () => {
    mocked.getGeneralAssessment.mockResolvedValue(makeAssessment());
    renderSection();

    await screen.findByTestId("general-score");
    const card = improvementCard("Bullet with no measurable result");
    fireEvent.click(within(card).getByRole("button", { name: "Approve" }));
    fireEvent.change(within(card).getByRole("textbox"), { target: { value: "Built dashboards used by 40 analysts." } });

    const submit = screen.getByRole("button", { name: "Create new version and recheck" });
    expect(submit).toBeDisabled();

    fireEvent.click(within(card).getByRole("checkbox"));
    expect(submit).toBeEnabled();
  });

  it("advisory items can only be rejected", async () => {
    mocked.getGeneralAssessment.mockResolvedValue(makeAssessment());
    renderSection();

    await screen.findByTestId("general-score");
    const card = improvementCard("Inconsistent heading capitalization");

    expect(within(card).queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Reject" })).toBeInTheDocument();
  });

  it("submits rejections only, without creating a version", async () => {
    mocked.getGeneralAssessment
      .mockResolvedValueOnce(makeAssessment())
      .mockResolvedValueOnce(
        makeAssessment({
          readiness: { state: "ready", open_count: 0, dismissed_count: 3 },
        }),
      );
    mocked.submitGeneralReview.mockResolvedValue(makeReview({ child_resume_version_id: null }));
    renderSection();

    await screen.findByTestId("general-score");
    for (const card of screen.getAllByTestId("improvement")) {
      fireEvent.click(within(card).getByRole("button", { name: "Reject" }));
    }
    fireEvent.click(screen.getByRole("button", { name: "Save review" }));

    await waitFor(() =>
      expect(mocked.submitGeneralReview).toHaveBeenCalledWith("version-1", "assessment-1", [
        { improvement_id: "imp-bullet", action: "reject" },
        { improvement_id: "imp-metric", action: "reject" },
        { improvement_id: "imp-advisory", action: "reject" },
      ]),
    );
    expect(await screen.findByTestId("ready-message")).toBeInTheDocument();
    expect(screen.getByText("Resume Ready")).toBeInTheDocument();
  });

  it("submits the user's own text for an approval", async () => {
    mocked.getGeneralAssessment.mockResolvedValue(makeAssessment());
    mocked.submitGeneralReview.mockResolvedValue(makeReview());
    renderSection();

    await screen.findByTestId("general-score");
    const card = improvementCard("Bullet with weak phrasing");
    fireEvent.click(within(card).getByRole("button", { name: "Approve" }));
    fireEvent.change(within(card).getByRole("textbox"), { target: { value: "Owned the checks." } });
    fireEvent.click(screen.getByRole("button", { name: "Create new version and recheck" }));

    await waitFor(() =>
      expect(mocked.submitGeneralReview).toHaveBeenCalledWith("version-1", "assessment-1", [
        {
          improvement_id: "imp-bullet",
          action: "approve",
          truth_confirmed: false,
          user_content: "Owned the checks.",
        },
      ]),
    );
  });

  it("shows the before/after comparison and opens the refined version", async () => {
    mocked.getGeneralAssessment.mockResolvedValue(
      makeAssessment({
        readiness: { state: "needs_review", open_count: 3, dismissed_count: 0 },
        latest_review: makeReview(),
      }),
    );
    const onOpen = renderSection();

    const outcome = await screen.findByTestId("review-outcome");
    expect(within(outcome).getByTestId("comparison-scores")).toHaveTextContent("72.5 → 80");
    expect(within(outcome).getByTestId("comparison-delta")).toHaveTextContent("+7.5");

    fireEvent.click(within(outcome).getByRole("button", { name: "Open Refined 1" }));
    expect(onOpen).toHaveBeenCalledWith("version-2");
  });

  it("keeps showing the parent's own readiness and improvements after a child is created", async () => {
    mocked.getGeneralAssessment.mockResolvedValue(
      makeAssessment({
        readiness: { state: "needs_review", open_count: 1, dismissed_count: 2 },
        latest_review: makeReview(),
      }),
    );
    renderSection();

    expect(await screen.findByTestId("review-outcome")).toBeInTheDocument();
    expect(screen.getByText("1 to review")).toBeInTheDocument();
    expect(screen.getAllByTestId("improvement")).toHaveLength(3);
    expect(screen.queryByText(/Refined version created/)).not.toBeInTheDocument();
  });

  it("shows no review outcome when the latest review created no version", async () => {
    mocked.getGeneralAssessment.mockResolvedValue(
      makeAssessment({ latest_review: makeReview({ child_resume_version_id: null, child_resume_version_name: null }) }),
    );
    renderSection();

    await screen.findByTestId("general-score");
    expect(screen.queryByTestId("review-outcome")).not.toBeInTheDocument();
  });

  it("reports a regression honestly", async () => {
    const review = makeReview();
    review.comparison = { ...review.comparison!, recheck_score: 70, score_delta: -2.5 };
    mocked.getGeneralAssessment.mockResolvedValue(
      makeAssessment({
        readiness: { state: "needs_review", open_count: 3, dismissed_count: 0 },
        latest_review: review,
      }),
    );
    renderSection();

    expect(await screen.findByTestId("comparison-delta")).toHaveTextContent("−2.5");
  });

  it("keeps the version and offers a retry when the recheck failed", async () => {
    const failed = makeReview({ recheck_status: "failed", recheck_error: "The recheck could not be completed.", comparison: null });
    mocked.getGeneralAssessment.mockResolvedValue(
      makeAssessment({
        readiness: { state: "needs_review", open_count: 3, dismissed_count: 0 },
        latest_review: failed,
      }),
    );
    mocked.retryGeneralRecheck.mockResolvedValue(makeReview());
    renderSection();

    // The failed recheck comes from the review, not from readiness: the
    // parent keeps its own "needs review" state.
    expect(await screen.findByText(/Your new version was saved\. Only the recheck\s+failed/)).toBeInTheDocument();
    expect(screen.getByText("3 to review")).toBeInTheDocument();
    expect(screen.queryByText("Recheck failed")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry recheck" }));
    await waitFor(() => expect(mocked.retryGeneralRecheck).toHaveBeenCalledWith("review-1"));
  });

  it("surfaces a server validation error", async () => {
    mocked.getGeneralAssessment.mockResolvedValue(makeAssessment());
    mocked.submitGeneralReview.mockRejectedValue(new Error("Confirm what you wrote is accurate."));
    renderSection();

    await screen.findByTestId("general-score");
    fireEvent.click(within(improvementCard("Bullet with weak phrasing")).getByRole("button", { name: "Reject" }));
    fireEvent.click(screen.getByRole("button", { name: "Save review" }));

    expect(await screen.findByText("Confirm what you wrote is accurate.")).toBeInTheDocument();
  });
});
