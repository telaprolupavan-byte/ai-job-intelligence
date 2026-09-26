// @vitest-environment jsdom
//
// AJI-019 regression: Job Match, ATS Alignment and Gap Analysis are each
// computed against one exact ResumeVersion. Switching the page-level
// Resume Version Selector must not leave a previous version's results on
// screen - they would read as belonging to the newly selected resume
// with nothing marking them stale.
//
// Hard Eligibility and Job Intelligence must survive the switch: neither
// reads the resume, so a resume change cannot invalidate them.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/jobs",
  useSearchParams: () => new URLSearchParams(),
}));

const calculateJobMatch = vi.fn();
const calculateAtsAlignment = vi.fn();
const calculateGapAnalysis = vi.fn();
const getJobEligibility = vi.fn();
const generateJobIntelligence = vi.fn();
const getJobs = vi.fn();

vi.mock("@/lib/jobs", () => ({
  getJobs: (...args: unknown[]) => getJobs(...args),
  calculateJobMatch: (...args: unknown[]) => calculateJobMatch(...args),
  calculateAtsAlignment: (...args: unknown[]) => calculateAtsAlignment(...args),
  calculateGapAnalysis: (...args: unknown[]) => calculateGapAnalysis(...args),
  getJobEligibility: (...args: unknown[]) => getJobEligibility(...args),
  generateJobIntelligence: (...args: unknown[]) =>
    generateJobIntelligence(...args),
}));

// AJI-024 discovery status: not what these tests exercise - report a
// configured, non-test source so no discovery notice renders.
vi.mock("@/lib/job-discovery", () => ({
  getDiscoveryStatus: () =>
    Promise.resolve({
      source_configured: true,
      test_mode: false,
      last_run: null,
    }),
}));

vi.mock("@/lib/resumes", () => ({
  getResumes: async () => [
    { id: "resume-1", filename: "cv.pdf", created_at: "2026-01-01T00:00:00Z" },
  ],
  getResumeVersions: async () => [
    {
      id: "version-1",
      name: "Original",
      is_master: true,
      created_at: "2026-01-01T00:00:00Z",
    },
    {
      id: "version-2",
      name: "Version 2",
      is_master: false,
      created_at: "2026-01-02T00:00:00Z",
    },
  ],
}));

// The real selector is a Base UI portal listbox; driving it in jsdom
// tests Base UI, not this page. What matters here is what the page does
// when a selection is made, so the selector is reduced to a button that
// reports one.
vi.mock("@/components/resume/resume-version-selector", () => ({
  default: ({ onSelect }: { onSelect: (id: string) => void }) => (
    <button type="button" onClick={() => onSelect("version-2")}>
      pick version 2
    </button>
  ),
}));

vi.mock("@/lib/applications", () => ({
  getApplications: async () => [],
  saveJob: vi.fn(),
  removeSavedJob: vi.fn(),
  updateApplicationStatus: vi.fn(),
}));

import JobsPage from "./page";

const JOB = {
  id: "job-1",
  title: "Senior AI Engineer",
  company: "Acme",
  location: "New York, NY",
  country: "USA",
  remote_type: "remote",
  employment_type: "full_time",
  salary_min: null,
  salary_max: null,
  salary_currency: null,
  contract_duration: null,
  contract_worker_type: null,
  description: "Build things.",
  requirements: "Python",
  responsibilities: "Ship.",
  posting_date: "2026-01-01T00:00:00Z",
  source: "greenhouse",
  source_url: null,
  application_url: null,
  first_seen_at: "2026-01-01T00:00:00Z",
  last_seen_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();

  getJobs.mockResolvedValue({
    jobs: [JOB],
    pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
  });

  calculateAtsAlignment.mockResolvedValue({
    id: "ats-1",
    job_id: "job-1",
    resume_version_id: "version-1",
    overall_score: 82,
    confidence: "high",
    must_have_total: 2,
    must_have_matched: 2,
    preferred_total: 1,
    preferred_matched: 1,
    requirement_results: [],
    score_components: [],
    relationships: [],
    screening_constraints: [],
    created_at: "2026-01-01T00:00:00Z",
  });

  calculateGapAnalysis.mockResolvedValue({
    id: "gap-1",
    job_id: "job-1",
    resume_version_id: "version-1",
    generation_status: "complete",
    must_have_gap_count: 1,
    preferred_gap_count: 0,
    gaps: [
      {
        requirement_id: "skill:kubernetes",
        requirement_type: "skill",
        category: "must_have",
        requirement_text: "Kubernetes",
        status: "missing",
        jd_evidence: "Kubernetes is required.",
        resume_evidence: null,
        suggestion_type: "ADD_IF_TRUE",
        explanation: "Your resume does not evidence Kubernetes.",
        explanation_source: "deterministic",
        suggestion_text: "Add Kubernetes if you have used it.",
        suggestion_source: "deterministic",
        confidence: "medium",
      },
    ],
    created_at: "2026-01-01T00:00:00Z",
  });

  getJobEligibility.mockResolvedValue({
    id: "elig-1",
    job_id: "job-1",
    status: "ELIGIBLE",
    engine_version: "1.0",
    checks: [],
    failed_constraints: [],
    unknown_constraints: [],
    reasons: [],
    evaluated_at: "2026-01-01T00:00:00Z",
  });
});

afterEach(() => {
  cleanup();
});

async function switchResumeVersion() {
  fireEvent.click(await screen.findByRole("button", { name: /pick version 2/i }));
}

describe("switching the selected resume version", () => {
  it("drops an ATS Alignment result computed for the previous version", async () => {
    render(<JobsPage />);

    fireEvent.click(
      await screen.findByRole("button", { name: /ATS Alignment/i }),
    );

    expect(await screen.findByText("82%")).toBeInTheDocument();

    await switchResumeVersion();

    await waitFor(() => {
      expect(screen.queryByText("82%")).not.toBeInTheDocument();
    });
  });

  it("drops a Gap Analysis result computed for the previous version", async () => {
    render(<JobsPage />);

    fireEvent.click(
      await screen.findByRole("button", { name: /Analyze job-specific gaps/i }),
    );

    expect(
      await screen.findByText("Your resume does not evidence Kubernetes."),
    ).toBeInTheDocument();

    await switchResumeVersion();

    await waitFor(() => {
      expect(
        screen.queryByText("Your resume does not evidence Kubernetes."),
      ).not.toBeInTheDocument();
    });
  });

  it("keeps Hard Eligibility, which does not depend on the resume", async () => {
    render(<JobsPage />);

    fireEvent.click(
      await screen.findByRole("button", { name: /eligibility/i }),
    );

    const eligible = await screen.findAllByText(/ELIGIBLE/i);
    expect(eligible.length).toBeGreaterThan(0);

    await switchResumeVersion();

    // Still there - a resume switch cannot invalidate an eligibility
    // result computed from profile/preferences vs. the job.
    expect(screen.getAllByText(/ELIGIBLE/i).length).toBeGreaterThan(0);
  });

  it("sends the newly selected version on the next calculation", async () => {
    render(<JobsPage />);

    await switchResumeVersion();

    fireEvent.click(
      await screen.findByRole("button", { name: /ATS Alignment/i }),
    );

    await waitFor(() => {
      expect(calculateAtsAlignment).toHaveBeenCalledWith("job-1", "version-2");
    });
  });
});
