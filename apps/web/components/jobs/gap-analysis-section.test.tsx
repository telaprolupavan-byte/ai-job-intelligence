// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

import GapAnalysisSection from "./gap-analysis-section";
import type { GapAnalysisResult, GapSuggestion } from "@/lib/jobs";

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
    explanation:
      "The job explicitly requires Kubernetes. Your selected resume does not contain evidence for this skill.",
    explanation_source: "ai",
    suggestion_text:
      "If you have hands-on Kubernetes experience, consider adding it.",
    suggestion_source: "ai",
    confidence: "high",
    ...overrides,
  };
}

function makeResult(
  overrides: Partial<GapAnalysisResult> = {},
): GapAnalysisResult {
  return {
    id: "gap-1",
    job_id: "job-1",
    resume_version_id: "resume-version-1",
    job_intelligence_id: "ji-1",
    ats_alignment_id: "ats-1",
    analysis_version: "v1",
    analyzer_version: "v1",
    prompt_version: "v1",
    model_provider: "openai",
    model_name: "gpt",
    generation_status: "complete",
    must_have_gap_count: 1,
    preferred_gap_count: 0,
    gaps: [makeGap()],
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("GapAnalysisSection", () => {
  it("renders the safety note and an idle 'Analyze Gaps' trigger before anything has run", () => {
    render(
      <GapAnalysisSection
        jobId="job-1"
        isLoading={false}
        onCalculate={vi.fn()}
      />,
    );

    expect(
      screen.getByText(/NERO only surfaces evidence-backed gaps/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /analyze job-specific gaps/i }),
    ).toBeInTheDocument();
  });

  it("shows a skeleton loading state with 'Analyzing this job…' while the request is in flight", () => {
    render(
      <GapAnalysisSection
        jobId="job-1"
        isLoading={true}
        onCalculate={vi.fn()}
      />,
    );

    expect(screen.getByText(/analyzing this job/i)).toBeInTheDocument();
    // No result content or error should render mid-flight.
    expect(screen.queryByText(/no meaningful gaps/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/gap analysis unavailable/i),
    ).not.toBeInTheDocument();
  });

  it("renders every returned suggestion on success, without inventing content beyond the API response", () => {
    const result = makeResult({
      gaps: [
        makeGap({
          requirement_id: "req-1",
          requirement_text: "Kubernetes",
          status: "missing",
          explanation: "No evidence for Kubernetes in the resume.",
        }),
        makeGap({
          requirement_id: "req-2",
          requirement_text: "Production observability",
          status: "missing",
          explanation: "No supporting evidence was found.",
        }),
        makeGap({
          requirement_id: "req-3",
          requirement_text: "Cloud platform evidence",
          status: "partial",
          suggestion_type: "REPHRASE_EXISTING",
          explanation:
            "Consider making your existing AWS experience more explicit.",
          resume_evidence: "Deployed services on AWS.",
        }),
      ],
    });

    render(
      <GapAnalysisSection
        jobId="job-1"
        result={result}
        isLoading={false}
        onCalculate={vi.fn()}
      />,
    );

    expect(screen.getByText("3 gaps")).toBeInTheDocument();
    expect(screen.getByText("Kubernetes")).toBeInTheDocument();
    expect(screen.getByText("Production observability")).toBeInTheDocument();
    expect(screen.getByText("Cloud platform evidence")).toBeInTheDocument();

    expect(screen.getAllByText("Missing")).toHaveLength(2);
    expect(screen.getAllByText("Improve")).toHaveLength(1);

    // Resume evidence, when present, is rendered verbatim.
    expect(
      screen.getByText(/Resume evidence: Deployed services on AWS\./),
    ).toBeInTheDocument();
    // No fabricated resume evidence for the two missing requirements.
    expect(
      screen.getAllByText(/No resume evidence found for this requirement\./),
    ).toHaveLength(2);
  });

  it("shows the 'No meaningful gaps found' empty state for a zero-gap result, not an error", () => {
    const result = makeResult({
      gaps: [],
      must_have_gap_count: 0,
      preferred_gap_count: 0,
    });

    render(
      <GapAnalysisSection
        jobId="job-1"
        result={result}
        isLoading={false}
        onCalculate={vi.fn()}
      />,
    );

    expect(screen.getByText("No meaningful gaps found")).toBeInTheDocument();
    expect(
      screen.getByText(/no job-specific gaps were identified/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/gap analysis unavailable/i),
    ).not.toBeInTheDocument();
  });

  it("shows 'Gap analysis unavailable' with a Retry action on error, and Retry re-triggers the request", () => {
    const onCalculate = vi.fn();

    render(
      <GapAnalysisSection
        jobId="job-42"
        isLoading={false}
        error="Unable to calculate Gap Analysis."
        onCalculate={onCalculate}
      />,
    );

    expect(screen.getByText("Gap analysis unavailable")).toBeInTheDocument();
    expect(
      screen.getByText(/unable to calculate gap analysis/i),
    ).toBeInTheDocument();

    const retryButton = screen.getByRole("button", { name: /retry/i });
    expect(retryButton).toBeInTheDocument();

    fireEvent.click(retryButton);

    expect(onCalculate).toHaveBeenCalledWith("job-42");
    expect(onCalculate).toHaveBeenCalledTimes(1);
  });

  it("passes the job id through to onCalculate so the caller can attach the currently selected resume version", () => {
    const onCalculate = vi.fn();

    render(
      <GapAnalysisSection
        jobId="job-7"
        isLoading={false}
        onCalculate={onCalculate}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: /analyze job-specific gaps/i }),
    );

    expect(onCalculate).toHaveBeenCalledWith("job-7");
  });

  it("does not crash on a partial response missing optional fields (evidence, explanation, suggestion type)", () => {
    const result = makeResult({
      gaps: [
        {
          requirement_id: "req-partial",
          requirement_type: "skill",
          category: "preferred",
          requirement_text: "",
          status: "missing",
          jd_evidence: "",
          resume_evidence: null,
          // @ts-expect-error - simulating a backend response omitting an
          // optional/nullable field to exercise the UI's fallback path.
          suggestion_type: undefined,
          explanation: "",
          explanation_source: "deterministic",
          suggestion_text: "",
          suggestion_source: "deterministic",
          confidence: "low",
        },
      ],
    });

    expect(() =>
      render(
        <GapAnalysisSection
          jobId="job-1"
          result={result}
          isLoading={false}
          onCalculate={vi.fn()}
        />,
      ),
    ).not.toThrow();

    expect(screen.getByText("Unspecified requirement")).toBeInTheDocument();
    expect(
      screen.getByText("No explanation was provided for this gap."),
    ).toBeInTheDocument();
  });

  it("shows the Recalculate label instead of Analyze Gaps once a result already exists", () => {
    render(
      <GapAnalysisSection
        jobId="job-1"
        result={makeResult()}
        isLoading={false}
        onCalculate={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("button", { name: /recalculate gap analysis/i }),
    ).toBeInTheDocument();
  });
});
