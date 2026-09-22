// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

import ResumeImprovementSection from "./resume-improvement-section";
import type {
  GapAnalysisResult,
  GapSuggestion,
  ResumeImprovementResult,
} from "@/lib/jobs";

afterEach(() => {
  cleanup();
});

function makeGap(overrides: Partial<GapSuggestion> = {}): GapSuggestion {
  return {
    requirement_id: "req-1",
    requirement_type: "skill",
    category: "must_have",
    requirement_text: "Kubernetes",
    status: "missing",
    jd_evidence: "The job explicitly requires Kubernetes.",
    resume_evidence: null,
    suggestion_type: "ADD_IF_TRUE",
    explanation: "No Kubernetes evidence was found in this resume version.",
    explanation_source: "deterministic",
    suggestion_text:
      "If you have hands-on Kubernetes experience, consider adding it.",
    suggestion_source: "deterministic",
    confidence: "high",
    ...overrides,
  };
}

function makeGapAnalysis(gaps: GapSuggestion[]): GapAnalysisResult {
  return {
    id: "gap-analysis-1",
    job_id: "job-1",
    resume_version_id: "version-1",
    job_intelligence_id: "ji-1",
    ats_alignment_id: "ats-1",
    analysis_version: "1.0",
    analyzer_version: "1.0",
    prompt_version: "1.0",
    model_provider: null,
    model_name: null,
    generation_status: "complete",
    must_have_gap_count: gaps.filter((g) => g.category === "must_have").length,
    preferred_gap_count: gaps.filter((g) => g.category === "preferred").length,
    gaps,
    created_at: new Date().toISOString(),
  };
}

function makeImprovement(
  overrides: Partial<ResumeImprovementResult> = {},
): ResumeImprovementResult {
  return {
    id: "improvement-1",
    job_id: "job-1",
    gap_analysis_id: "gap-analysis-1",
    baseline_ats_alignment_id: "ats-1",
    parent_resume_version_id: "version-1",
    child_resume_version_id: "version-2",
    child_resume_version_name: "Improved 1",
    engine_version: "1.0",
    approved_count: 1,
    skipped_count: 0,
    recheck_status: "complete",
    recheck_error: null,
    recheck_ats_alignment_id: "ats-2",
    decisions: [
      {
        requirement_id: "req-1",
        requirement_text: "Kubernetes",
        category: "must_have",
        suggestion_type: "ADD_IF_TRUE",
        action: "approve",
        truth_confirmed: true,
        applied_text: "Operated Kubernetes clusters at Acme.",
        content_source: "user",
      },
    ],
    comparison: {
      baseline_ats_alignment_id: "ats-1",
      baseline_resume_version_id: "version-1",
      baseline_score: 61,
      baseline_must_have_matched: 1,
      baseline_must_have_total: 2,
      baseline_preferred_matched: 1,
      baseline_preferred_total: 1,
      recheck_ats_alignment_id: "ats-2",
      recheck_resume_version_id: "version-2",
      recheck_score: 78,
      recheck_must_have_matched: 2,
      recheck_must_have_total: 2,
      recheck_preferred_matched: 1,
      recheck_preferred_total: 1,
      score_delta: 17,
      must_have_delta: 1,
      preferred_delta: 0,
      improved_count: 1,
      unchanged_count: 1,
      regressed_count: 0,
      transitions: [
        {
          requirement_id: "req-1",
          requirement_text: "Kubernetes",
          category: "must_have",
          before_status: "missing",
          after_status: "matched",
          direction: "improved",
          was_approved: true,
        },
        {
          requirement_id: "req-2",
          requirement_text: "SQL",
          category: "preferred",
          before_status: "matched",
          after_status: "matched",
          direction: "unchanged",
          was_approved: false,
        },
      ],
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

function renderSection(props: Partial<
  React.ComponentProps<typeof ResumeImprovementSection>
> = {}) {
  const onApprove = vi.fn();
  const onRetryRecheck = vi.fn();

  render(
    <ResumeImprovementSection
      jobId="job-1"
      isSubmitting={false}
      isRechecking={false}
      onApprove={onApprove}
      onRetryRecheck={onRetryRecheck}
      {...props}
    />,
  );

  return { onApprove, onRetryRecheck };
}

function approve(requirementText: string) {
  fireEvent.click(
    within(
      screen.getByRole("group", { name: `Decision for ${requirementText}` }),
    ).getByRole("button", { name: "Approve" }),
  );
}

describe("ResumeImprovementSection", () => {
  // -------------------------------------------------------------------
  // Rule: approval is mandatory, and nothing is applied without it
  // -------------------------------------------------------------------

  it("starts with every suggestion skipped and the create action blocked", () => {
    renderSection({ gapAnalysis: makeGapAnalysis([makeGap()]) });

    expect(screen.getByText("0 approved · 1 skipped")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /create new version/i }),
    ).toBeDisabled();
    expect(
      screen.getByText("Approve at least one suggestion."),
    ).toBeInTheDocument();
  });

  it("never calls onApprove while the action is blocked", () => {
    const { onApprove } = renderSection({
      gapAnalysis: makeGapAnalysis([makeGap()]),
    });

    fireEvent.click(
      screen.getByRole("button", { name: /create new version/i }),
    );

    expect(onApprove).not.toHaveBeenCalled();
  });

  // -------------------------------------------------------------------
  // Rule: ADD_IF_TRUE requires explicit truth confirmation
  // -------------------------------------------------------------------

  it("blocks an approved ADD_IF_TRUE suggestion until it is confirmed accurate", () => {
    renderSection({ gapAnalysis: makeGapAnalysis([makeGap()]) });

    approve("Kubernetes");
    fireEvent.change(screen.getByLabelText(/your wording/i), {
      target: { value: "Operated Kubernetes clusters at Acme." },
    });

    expect(
      screen.getByRole("button", { name: /create new version/i }),
    ).toBeDisabled();
    expect(
      screen.getByText("Confirm 1 added item is accurate."),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox"));

    expect(
      screen.getByRole("button", { name: /create new version/i }),
    ).toBeEnabled();
  });

  it("does not show a truth-confirmation box for a rephrase suggestion", () => {
    renderSection({
      gapAnalysis: makeGapAnalysis([
        makeGap({
          status: "partial",
          suggestion_type: "REPHRASE_EXISTING",
          resume_evidence: "Resume lists Kubernetes in a skills section.",
        }),
      ]),
    });

    approve("Kubernetes");

    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("clears the confirmation when a suggestion is switched back to skip", () => {
    const { onApprove } = renderSection({
      gapAnalysis: makeGapAnalysis([makeGap(), makeGap({
        requirement_id: "req-2",
        requirement_text: "Terraform",
      })]),
    });

    approve("Kubernetes");
    fireEvent.change(screen.getByLabelText(/your wording/i), {
      target: { value: "Operated Kubernetes clusters." },
    });
    fireEvent.click(screen.getByRole("checkbox"));

    // Switch it back to Skip, then approve the other one instead.
    fireEvent.click(
      within(
        screen.getByRole("group", { name: "Decision for Kubernetes" }),
      ).getByRole("button", { name: "Skip" }),
    );

    approve("Terraform");
    fireEvent.change(screen.getByLabelText(/your wording/i), {
      target: { value: "Wrote Terraform modules." },
    });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(
      screen.getByRole("button", { name: /create new version/i }),
    );

    const [, , decisions] = onApprove.mock.calls[0];
    const kubernetes = decisions.find(
      (d: { requirement_id: string }) => d.requirement_id === "req-1",
    );

    expect(kubernetes).toEqual({ requirement_id: "req-1", action: "skip" });
  });

  // -------------------------------------------------------------------
  // Rule: NERO never writes resume content
  // -------------------------------------------------------------------

  it("leaves the content box empty rather than pre-filling the suggestion text", () => {
    renderSection({ gapAnalysis: makeGapAnalysis([makeGap()]) });

    approve("Kubernetes");

    const textarea = screen.getByLabelText(/your wording/i) as HTMLTextAreaElement;

    expect(textarea.value).toBe("");
    // The suggestion is shown as advice, never as resume content.
    expect(
      screen.getByText(/If you have hands-on Kubernetes experience/i),
    ).toBeInTheDocument();
  });

  it("blocks an approval whose content box is empty or whitespace", () => {
    renderSection({ gapAnalysis: makeGapAnalysis([makeGap()]) });

    approve("Kubernetes");
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.change(screen.getByLabelText(/your wording/i), {
      target: { value: "   " },
    });

    expect(
      screen.getByRole("button", { name: /create new version/i }),
    ).toBeDisabled();
    expect(
      screen.getByText("Add your own wording for 1 approved suggestion."),
    ).toBeInTheDocument();
  });

  it("submits only the user's own text, with no suggestion_type field", () => {
    const { onApprove } = renderSection({
      gapAnalysis: makeGapAnalysis([makeGap()]),
    });

    approve("Kubernetes");
    fireEvent.change(screen.getByLabelText(/your wording/i), {
      target: { value: "  Operated Kubernetes clusters at Acme.  " },
    });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(
      screen.getByRole("button", { name: /create new version/i }),
    );

    expect(onApprove).toHaveBeenCalledWith("job-1", "gap-analysis-1", [
      {
        requirement_id: "req-1",
        action: "approve",
        truth_confirmed: true,
        user_content: "Operated Kubernetes clusters at Acme.",
      },
    ]);

    const [, , decisions] = onApprove.mock.calls[0];
    expect(decisions[0]).not.toHaveProperty("suggestion_type");
    expect(decisions[0]).not.toHaveProperty("applied_text");
  });

  // -------------------------------------------------------------------
  // States
  // -------------------------------------------------------------------

  it("asks the user to run Gap Analysis first when none exists", () => {
    renderSection();

    expect(screen.getByText("Run Gap Analysis first")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /create new version/i }),
    ).not.toBeInTheDocument();
  });

  it("shows a nothing-to-approve state for a zero-gap analysis", () => {
    renderSection({ gapAnalysis: makeGapAnalysis([]) });

    expect(screen.getByText("Nothing to approve")).toBeInTheDocument();
  });

  it("shows a progress state while the version is being created", () => {
    renderSection({
      gapAnalysis: makeGapAnalysis([makeGap()]),
      isSubmitting: true,
    });

    expect(
      screen.getByText(/creating your new version and rechecking/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /create new version/i }),
    ).not.toBeInTheDocument();
  });

  it("keeps the typed content and reassures the user on error", () => {
    renderSection({
      gapAnalysis: makeGapAnalysis([makeGap()]),
      error: "Approve at least one suggestion to create a new resume version.",
    });

    approve("Kubernetes");
    fireEvent.change(screen.getByLabelText(/your wording/i), {
      target: { value: "My own wording." },
    });

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/nothing was changed/i);
    expect(
      (screen.getByLabelText(/your wording/i) as HTMLTextAreaElement).value,
    ).toBe("My own wording.");
  });

  // -------------------------------------------------------------------
  // Compare
  // -------------------------------------------------------------------

  it("shows the before/after comparison once the recheck completes", () => {
    renderSection({
      gapAnalysis: makeGapAnalysis([makeGap()]),
      result: makeImprovement(),
    });

    expect(screen.getByText("Improved 1 created")).toBeInTheDocument();
    expect(screen.getByText("Before")).toBeInTheDocument();
    // Rendered with the `%` unit, matching the approved ATS Alignment
    // card that shows the same value on this page.
    expect(screen.getByText("61%")).toBeInTheDocument();
    expect(screen.getByText("After")).toBeInTheDocument();
    expect(screen.getByText("78%")).toBeInTheDocument();
    expect(screen.getByText("+17 ATS")).toBeInTheDocument();
    expect(screen.getByText("1 improved")).toBeInTheDocument();
    expect(screen.getByText("missing → matched")).toBeInTheDocument();
  });

  it("reports a score drop faithfully instead of hiding it", () => {
    const improvement = makeImprovement();
    improvement.comparison = {
      ...improvement.comparison!,
      recheck_score: 55,
      score_delta: -6,
      improved_count: 0,
      regressed_count: 1,
      transitions: [
        {
          requirement_id: "req-1",
          requirement_text: "Kubernetes",
          category: "must_have",
          before_status: "matched",
          after_status: "partial",
          direction: "regressed",
          was_approved: true,
        },
      ],
    };

    renderSection({
      gapAnalysis: makeGapAnalysis([makeGap()]),
      result: improvement,
    });

    expect(screen.getByText("-6 ATS")).toBeInTheDocument();
    expect(screen.getByText("1 regressed")).toBeInTheDocument();
    expect(screen.getByText("Regressed")).toBeInTheDocument();
  });

  it("states the new version is safe when the recheck failed, and offers a retry", () => {
    const { onRetryRecheck } = renderSection({
      gapAnalysis: makeGapAnalysis([makeGap()]),
      result: makeImprovement({
        recheck_status: "failed",
        recheck_error: "Requirement Intelligence is unavailable.",
        recheck_ats_alignment_id: null,
        comparison: null,
      }),
    });

    expect(screen.getByText("Improved 1 created")).toBeInTheDocument();
    expect(screen.getByText("Recheck didn't finish")).toBeInTheDocument();
    expect(
      screen.getByText(/your new version was saved and is safe/i),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /retry recheck/i }));

    expect(onRetryRecheck).toHaveBeenCalledWith("job-1", "improvement-1");
  });

  it("lets the user reopen the review list without losing the created version", () => {
    renderSection({
      gapAnalysis: makeGapAnalysis([makeGap()]),
      result: makeImprovement(),
    });

    fireEvent.click(
      screen.getByRole("button", { name: /review suggestions again/i }),
    );

    expect(
      screen.getByText(/approving a different set creates another new version/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /create new version/i }),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /back to comparison/i }),
    );

    expect(screen.getByText("Improved 1 created")).toBeInTheDocument();
  });

  it("returns to the comparison once a resubmission from the review list finishes", () => {
    const result = makeImprovement();

    const { rerender } = render(
      <ResumeImprovementSection
        jobId="job-1"
        gapAnalysis={makeGapAnalysis([makeGap()])}
        result={result}
        isSubmitting={false}
        isRechecking={false}
        onApprove={vi.fn()}
        onRetryRecheck={vi.fn()}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: /review suggestions again/i }),
    );
    expect(
      screen.getByRole("button", { name: /create new version/i }),
    ).toBeInTheDocument();

    const props = {
      jobId: "job-1",
      gapAnalysis: makeGapAnalysis([makeGap()]),
      isRechecking: false,
      onApprove: vi.fn(),
      onRetryRecheck: vi.fn(),
    };

    rerender(
      <ResumeImprovementSection {...props} result={result} isSubmitting={true} />,
    );
    // The same record comes back — re-approving an identical set never
    // creates a second version — and the user must still land on it.
    rerender(
      <ResumeImprovementSection {...props} result={result} isSubmitting={false} />,
    );

    expect(screen.getByText("Improved 1 created")).toBeInTheDocument();
  });

  it("stays on the review list when a resubmission fails, keeping the notes", () => {
    const result = makeImprovement();
    const props = {
      jobId: "job-1",
      gapAnalysis: makeGapAnalysis([makeGap()]),
      isRechecking: false,
      onApprove: vi.fn(),
      onRetryRecheck: vi.fn(),
    };

    const { rerender } = render(
      <ResumeImprovementSection {...props} result={result} isSubmitting={false} />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: /review suggestions again/i }),
    );

    rerender(
      <ResumeImprovementSection {...props} result={result} isSubmitting={true} />,
    );
    rerender(
      <ResumeImprovementSection
        {...props}
        result={result}
        isSubmitting={false}
        error="Approve at least one suggestion to create a new resume version."
      />,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /create new version/i }),
    ).toBeInTheDocument();
  });

  it("does not crash on a result whose comparison is missing", () => {
    expect(() =>
      renderSection({
        gapAnalysis: makeGapAnalysis([makeGap()]),
        result: makeImprovement({
          recheck_status: "pending",
          comparison: null,
          recheck_ats_alignment_id: null,
        }),
      }),
    ).not.toThrow();

    expect(screen.getByText("Improved 1 created")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------
  // Accessibility / interaction states
  // -------------------------------------------------------------------

  it("exposes the approve/skip choice as pressed toggles", () => {
    renderSection({ gapAnalysis: makeGapAnalysis([makeGap()]) });

    const group = screen.getByRole("group", { name: "Decision for Kubernetes" });
    const approveButton = within(group).getByRole("button", { name: "Approve" });
    const skipButton = within(group).getByRole("button", { name: "Skip" });

    expect(skipButton).toHaveAttribute("aria-pressed", "true");
    expect(approveButton).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(approveButton);

    expect(approveButton).toHaveAttribute("aria-pressed", "true");
    expect(skipButton).toHaveAttribute("aria-pressed", "false");
  });

  it("keeps each suggestion's decision independent of the others", () => {
    const { onApprove } = renderSection({
      gapAnalysis: makeGapAnalysis([
        makeGap(),
        makeGap({
          requirement_id: "req-2",
          requirement_text: "SQL",
          category: "preferred",
          status: "partial",
          suggestion_type: "REPHRASE_EXISTING",
          resume_evidence: "Resume lists SQL in a skills section.",
        }),
      ]),
    });

    approve("SQL");
    fireEvent.change(screen.getByLabelText(/your wording/i), {
      target: { value: "Wrote reporting SQL against a 2TB warehouse." },
    });

    expect(screen.getByText("1 approved · 1 skipped")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /create new version/i }),
    );

    const [, , decisions] = onApprove.mock.calls[0];
    expect(decisions).toEqual([
      { requirement_id: "req-1", action: "skip" },
      {
        requirement_id: "req-2",
        action: "approve",
        truth_confirmed: false,
        user_content: "Wrote reporting SQL against a 2TB warehouse.",
      },
    ]);
  });

  it("marks the current workflow step", () => {
    renderSection({
      gapAnalysis: makeGapAnalysis([makeGap()]),
      result: makeImprovement(),
    });

    expect(screen.getByText("Compare")).toHaveAttribute("aria-current", "step");
  });
});
