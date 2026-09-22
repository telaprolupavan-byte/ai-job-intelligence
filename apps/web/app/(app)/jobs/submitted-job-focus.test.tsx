// @vitest-environment jsdom
//
// AJI-022 — the Jobs page's "Add a job" entry point (Figma 133:266/267)
// and the `?job=<id>` destination a successful submission lands on: that
// one job's card with its Job Intelligence loaded.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

const replace = vi.fn();
let searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/jobs",
  useSearchParams: () => searchParams,
}));

const getJobs = vi.fn();
const getJob = vi.fn();
const generateJobIntelligence = vi.fn();

vi.mock("@/lib/jobs", () => ({
  getJobs: (...args: unknown[]) => getJobs(...args),
  getJob: (...args: unknown[]) => getJob(...args),
  generateJobIntelligence: (...args: unknown[]) =>
    generateJobIntelligence(...args),
  calculateJobMatch: vi.fn(),
  calculateAtsAlignment: vi.fn(),
  calculateGapAnalysis: vi.fn(),
  getJobEligibility: vi.fn(),
  createResumeImprovement: vi.fn(),
  runResumeImprovementRecheck: vi.fn(),
}));

vi.mock("@/lib/resumes", () => ({
  getResumes: async () => [],
  getResumeVersions: async () => [],
}));

vi.mock("@/lib/applications", () => ({
  getApplications: async () => [],
  saveJob: vi.fn(),
  removeSavedJob: vi.fn(),
  updateApplicationStatus: vi.fn(),
}));

import JobsPage from "./page";

const SUBMITTED_JOB = {
  id: "job-submitted",
  title: "Senior Backend Engineer",
  company: "Acme",
  location: null,
  country: "",
  remote_type: null,
  employment_type: null,
  salary_min: null,
  salary_max: null,
  salary_currency: null,
  contract_duration: null,
  contract_worker_type: null,
  description: "Acme builds payments infrastructure.",
  requirements: "Requirements\n- 5+ years of Python",
  responsibilities: null,
  posting_date: null,
  source: "user_submitted",
  source_url: null,
  application_url: null,
  first_seen_at: "2026-09-22T00:00:00",
  last_seen_at: "2026-09-22T00:00:00",
  raw_submitted_content: "Senior Backend Engineer\n...",
};

const INTELLIGENCE = {
  id: "ji-1",
  job_id: "job-submitted",
  analysis_version: "1.0",
  extraction_status: "complete",
  created_at: "2026-09-22T00:00:00",
  intelligence: {
    identity: {
      original_title: "Senior Backend Engineer",
      normalized_title: "Backend Engineer",
      role_family: null,
      seniority: "Senior",
    },
    employment: { employment_type: "unknown", evidence_text: null },
    location: {
      raw_location: null,
      city: null,
      state: null,
      country: null,
      additional_locations: [],
      remote_type: "unknown",
      work_arrangement_text: null,
      relocation_mentioned: false,
    },
    required_skills: [
      {
        canonical_skill: "Python",
        level: "required",
        evidence_text: "5+ years of Python",
        confidence: "high",
      },
    ],
    preferred_skills: [],
    required_experience: [],
    preferred_experience: [],
    education: [],
    certifications: [],
    responsibilities: [],
    authorization: {
      sponsorship: "unknown",
      citizenship: "unknown",
      clearance: "unknown",
      work_authorization: "unknown",
    },
    compensation: {
      salary_min: null,
      salary_max: null,
      currency: null,
      period: "unknown",
      evidence_text: null,
    },
    domain: { value: null, confidence: null },
  },
};

describe("Jobs page — AJI-022 submission entry and destination", () => {
  beforeEach(() => {
    searchParams = new URLSearchParams();
    replace.mockReset();
    getJob.mockReset();
    generateJobIntelligence.mockReset();
    getJobs.mockReset();
    getJobs.mockResolvedValue({
      jobs: [],
      pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 },
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("links to the Submit Job screen from the Jobs header", async () => {
    render(<JobsPage />);

    expect(
      await screen.findByRole("link", { name: "Add a job" }),
    ).toHaveAttribute("href", "/jobs/submit");
    expect(getJob).not.toHaveBeenCalled();
  });

  it("opens the submitted job with its Job Intelligence loaded", async () => {
    searchParams = new URLSearchParams("job=job-submitted");
    getJob.mockResolvedValue(SUBMITTED_JOB);
    generateJobIntelligence.mockResolvedValue(INTELLIGENCE);

    render(<JobsPage />);

    expect(
      await screen.findByRole("heading", { name: "Senior Backend Engineer" }),
    ).toBeInTheDocument();
    expect(getJob).toHaveBeenCalledWith("job-submitted");
    await waitFor(() =>
      expect(generateJobIntelligence).toHaveBeenCalledWith("job-submitted"),
    );
    expect(await screen.findByText("Backend Engineer")).toBeInTheDocument();

    // The discovery filters/list are replaced by this one job...
    expect(screen.queryByText("Search Parameters")).not.toBeInTheDocument();
    // ...and the focused job survives the page's URL sync.
    expect(replace).toHaveBeenLastCalledWith("/jobs?job=job-submitted", {
      scroll: false,
    });

    fireEvent.click(screen.getByRole("button", { name: "← All jobs" }));

    expect(await screen.findByText("Search Parameters")).toBeInTheDocument();
    await waitFor(() =>
      expect(replace).toHaveBeenLastCalledWith("/jobs", { scroll: false }),
    );
  });

  it("shows an error when the job cannot be opened (e.g. another user's)", async () => {
    searchParams = new URLSearchParams("job=someone-elses");
    getJob.mockRejectedValue(new Error("Job not found"));

    render(<JobsPage />);

    expect(await screen.findByText("Job not found")).toBeInTheDocument();
    expect(generateJobIntelligence).not.toHaveBeenCalled();
  });
});
