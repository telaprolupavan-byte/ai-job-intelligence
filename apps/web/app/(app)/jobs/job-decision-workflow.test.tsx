// @vitest-environment jsdom
//
// AJI-023 — Job Intelligence -> Application Decision Workflow on the Jobs
// page: opening a job, its saved results, the no-resume / denied / error
// states, and the Save / Mark Applied tracking actions.
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { ApiError } from "@/lib/api";

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
const getJobEligibility = vi.fn();
const getLatestJobResults = vi.fn();
const calculateJobMatch = vi.fn();

vi.mock("@/lib/jobs", () => ({
  getJobs: (...args: unknown[]) => getJobs(...args),
  getJob: (...args: unknown[]) => getJob(...args),
  generateJobIntelligence: (...args: unknown[]) =>
    generateJobIntelligence(...args),
  getJobEligibility: (...args: unknown[]) => getJobEligibility(...args),
  getLatestJobResults: (...args: unknown[]) => getLatestJobResults(...args),
  calculateJobMatch: (...args: unknown[]) => calculateJobMatch(...args),
  calculateAtsAlignment: vi.fn(),
  calculateGapAnalysis: vi.fn(),
  createResumeImprovement: vi.fn(),
  runResumeImprovementRecheck: vi.fn(),
}));

const getResumes = vi.fn();
const getResumeVersions = vi.fn();

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
  getResumes: (...args: unknown[]) => getResumes(...args),
  getResumeVersions: (...args: unknown[]) => getResumeVersions(...args),
}));

const getApplications = vi.fn();
const saveJob = vi.fn();
const updateApplicationStatus = vi.fn();

vi.mock("@/lib/applications", () => ({
  getApplications: (...args: unknown[]) => getApplications(...args),
  saveJob: (...args: unknown[]) => saveJob(...args),
  updateApplicationStatus: (...args: unknown[]) =>
    updateApplicationStatus(...args),
  removeSavedJob: vi.fn(),
}));

import JobsPage from "./page";

const JOB = {
  id: "job-1",
  title: "Data Engineer",
  company: "Acme",
  location: "Remote",
  country: "USA",
  remote_type: "remote",
  employment_type: "full_time",
  salary_min: null,
  salary_max: null,
  salary_currency: null,
  contract_duration: null,
  contract_worker_type: null,
  description: "Build pipelines.",
  requirements: null,
  responsibilities: null,
  posting_date: null,
  source: "greenhouse",
  source_url: null,
  application_url: "https://example.com/apply",
  first_seen_at: "2026-09-22T00:00:00",
  last_seen_at: "2026-09-22T00:00:00",
};

const INTELLIGENCE_RESPONSE = {
  id: "ji-1",
  job_id: "job-1",
  analysis_version: "1.0",
  extraction_status: "partial",
  created_at: "2026-09-22T00:00:00",
  intelligence: {
    identity: {
      original_title: "Data Engineer",
      normalized_title: "Data Engineer",
      role_family: "data",
      seniority: "mid",
    },
    employment: { employment_type: "full_time", evidence_text: null },
    location: {
      raw_location: "Remote",
      city: null,
      state: null,
      country: "USA",
      additional_locations: [],
      remote_type: "remote",
      work_arrangement_text: "Fully remote",
      relocation_mentioned: false,
    },
    required_skills: [
      {
        canonical_skill: "Python",
        level: "required",
        evidence_text: "Strong Python",
        confidence: "high",
      },
    ],
    preferred_skills: [],
    required_experience: [],
    preferred_experience: [],
    education: [
      {
        level: "required",
        degree_level: "bachelors",
        field_of_study: "computer_science",
        evidence_text: "BS in Computer Science",
        confidence: "high",
      },
    ],
    certifications: [],
    responsibilities: [
      { description: "Own the ingestion pipeline", evidence_text: "Own" },
    ],
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
    domain: { value: "Fintech", confidence: "medium" },
  },
};

const ELIGIBILITY = {
  id: "el-1",
  job_id: "job-1",
  status: "eligible",
  engine_version: "1",
  checks: [],
  failed_constraints: [],
  unknown_constraints: [],
  reasons: [],
  evaluated_at: "2026-09-22T00:00:00",
};

const SAVED_MATCH = {
  id: "match-1",
  job_id: "job-1",
  resume_version_id: "rv-master",
  job_intelligence_id: "ji-1",
  score: 72,
  confidence: "medium",
  engine_version: "1.0.0",
  strengths: [],
  skill_gaps: [],
  components: [],
  must_have_matches: [],
  must_have_gaps: [],
  preferred_matches: [],
  preferred_gaps: [],
};

const SAVED_ATS = {
  id: "ats-1",
  job_id: "job-1",
  resume_version_id: "rv-master",
  job_intelligence_id: "ji-1",
  engine_version: "1",
  overall_score: 58,
  confidence: "medium",
  scoring_version: "1",
  must_have_total: 2,
  must_have_matched: 1,
  preferred_total: 0,
  preferred_matched: 0,
  must_have_ceiling: null,
  score_components: [],
  requirement_results: [
    {
      requirement_id: "r-python",
      requirement_type: "skill",
      category: "must_have",
      requirement_text: "Python",
      status: "matched",
      jd_evidence: "Strong Python",
      resume_evidence: "Python",
      explanation: "Found",
      confidence: "high",
    },
    {
      requirement_id: "r-spark",
      requirement_type: "skill",
      category: "must_have",
      requirement_text: "Apache Spark",
      status: "missing",
      jd_evidence: "Spark",
      resume_evidence: null,
      explanation: "Not found",
      confidence: "high",
    },
  ],
  created_at: "2026-09-22T00:00:00",
};

function renderFocused(jobId = "job-1") {
  searchParams = new URLSearchParams(`job=${jobId}`);
  return render(<JobsPage />);
}

function workflowPanel() {
  return screen
    .getByRole("heading", { name: "Understand this job, then decide" })
    .closest("section") as HTMLElement;
}

describe("Jobs page — AJI-023 decision workflow", () => {
  beforeEach(() => {
    searchParams = new URLSearchParams();
    replace.mockReset();
    getJobs.mockReset().mockResolvedValue({
      jobs: [],
      pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 },
    });
    getJob.mockReset().mockResolvedValue(JOB);
    generateJobIntelligence.mockReset().mockResolvedValue(INTELLIGENCE_RESPONSE);
    getJobEligibility.mockReset().mockResolvedValue(ELIGIBILITY);
    getLatestJobResults.mockReset().mockResolvedValue({
      match: null,
      ats: null,
      gapAnalysis: null,
      improvement: null,
    });
    calculateJobMatch.mockReset();
    getResumes
      .mockReset()
      .mockResolvedValue([{ id: "resume-1", filename: "resume.pdf" }]);
    getResumeVersions.mockReset().mockResolvedValue([
      {
        id: "rv-master",
        name: "Master",
        is_master: true,
        created_at: "2026-09-01T00:00:00",
      },
    ]);
    getApplications.mockReset().mockResolvedValue([]);
    saveJob.mockReset();
    updateApplicationStatus.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("opens a listed job into its workflow view", async () => {
    getJobs.mockResolvedValue({
      jobs: [JOB],
      pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
    });

    render(<JobsPage />);

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Open job workflow for Data Engineer",
      }),
    );

    expect(
      await screen.findByRole("heading", {
        name: "Understand this job, then decide",
      }),
    ).toBeInTheDocument();
    expect(getJob).toHaveBeenCalledWith("job-1");
    await waitFor(() =>
      expect(replace).toHaveBeenLastCalledWith("/jobs?job=job-1", {
        scroll: false,
      }),
    );
  });

  it("loads Job Intelligence, eligibility and saved results for the version shown", async () => {
    getLatestJobResults.mockResolvedValue({
      match: SAVED_MATCH,
      ats: SAVED_ATS,
      gapAnalysis: null,
      improvement: null,
    });

    renderFocused();

    const panel = await screen.findByRole("heading", {
      name: "Understand this job, then decide",
    });
    const section = panel.closest("section") as HTMLElement;

    await waitFor(() =>
      expect(getLatestJobResults).toHaveBeenCalledWith("job-1", "rv-master"),
    );
    expect(generateJobIntelligence).toHaveBeenCalledWith("job-1");
    expect(getJobEligibility).toHaveBeenCalledWith("job-1");

    // Each result on its own stage - never blended.
    expect(
      await within(section).findByText("72% · medium confidence"),
    ).toBeInTheDocument();
    expect(within(section).getByText("58% · must-have 1/2")).toBeInTheDocument();
    expect(within(section).getByText("Not analyzed yet.")).toBeInTheDocument();

    // Alignment and missing requirements come from the ATS result.
    expect(within(section).getByText("Apache Spark")).toBeInTheDocument();
    expect(
      within(section).getByText("Master (resume.pdf)"),
    ).toBeInTheDocument();

    // The next step is the first stage without a result.
    expect(within(section).getByText("Analyze gaps", { selector: "p" })).toBeInTheDocument();

    // Deterministic-only Job Intelligence is labelled as such.
    expect(
      screen.getByText(/Deterministic extraction only/),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Bachelors — Computer Science"),
    ).toBeInTheDocument();
    expect(screen.getByText("Own the ingestion pipeline")).toBeInTheDocument();
  });

  it("shows the no-resume state and never requests resume-based results", async () => {
    getResumes.mockResolvedValue([]);

    renderFocused();

    expect(
      await screen.findByRole("link", { name: "Go to Resume" }),
    ).toHaveAttribute("href", "/resume");
    const section = workflowPanel();
    expect(
      within(section).getAllByText("Upload a resume to calculate."),
    ).toHaveLength(4);
    expect(getLatestJobResults).not.toHaveBeenCalled();
  });

  it("runs a stage from the workflow and retries it after a failure", async () => {
    calculateJobMatch
      .mockRejectedValueOnce(new Error("Match service unavailable."))
      .mockResolvedValueOnce(SAVED_MATCH);

    renderFocused();

    // The stage shows "Loading saved result…" until the read settles.
    await waitFor(() => expect(getLatestJobResults).toHaveBeenCalled());
    expect(
      await screen.findAllByText("Not calculated yet."),
    ).not.toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Run Job Match" }));

    const section = workflowPanel();
    expect(
      await within(section).findByText("Match service unavailable."),
    ).toBeInTheDocument();

    fireEvent.click(within(section).getByRole("button", { name: "Retry Job Match" }));

    expect(
      await within(section).findByText("72% · medium confidence"),
    ).toBeInTheDocument();
    expect(calculateJobMatch).toHaveBeenLastCalledWith("job-1", undefined);
  });

  it("offers a retry when saved results fail to load", async () => {
    getLatestJobResults
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValueOnce({
        match: SAVED_MATCH,
        ats: null,
        gapAnalysis: null,
        improvement: null,
      });

    renderFocused();

    expect(
      await screen.findByText(/Couldn't load your saved results/),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(
      await screen.findByText("72% · medium confidence"),
    ).toBeInTheDocument();
    expect(getLatestJobResults).toHaveBeenCalledTimes(2);
  });

  it("denies another user's private job without confirming it exists", async () => {
    getJob.mockRejectedValue(new ApiError("Job not found", 404));

    renderFocused("someone-elses-job");

    expect(await screen.findByText("Job unavailable")).toBeInTheDocument();
    expect(
      screen.getByText(/doesn't exist or isn't available to your account/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Try Again" })).toBeNull();
    expect(generateJobIntelligence).not.toHaveBeenCalled();
    expect(getLatestJobResults).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Back to all jobs" }));
    expect(await screen.findByText("Search Parameters")).toBeInTheDocument();
  });

  it("retries a job that failed to load for a transient reason", async () => {
    getJob
      .mockRejectedValueOnce(new ApiError("Service unavailable", 503))
      .mockResolvedValueOnce(JOB);

    renderFocused();

    fireEvent.click(await screen.findByRole("button", { name: "Try Again" }));

    expect(
      await screen.findByRole("heading", {
        name: "Understand this job, then decide",
      }),
    ).toBeInTheDocument();
    expect(getJob).toHaveBeenCalledTimes(2);
  });

  it("marks an untracked job applied by saving it first — never applying", async () => {
    saveJob.mockResolvedValue({ id: "app-1", status: "saved", job: JOB });
    updateApplicationStatus.mockResolvedValue({
      id: "app-1",
      status: "applied",
      job: JOB,
    });

    renderFocused();

    await screen.findByRole("heading", {
      name: "Understand this job, then decide",
    });
    const section = workflowPanel();

    // Tracking controls live once, in the workflow panel.
    expect(screen.getAllByRole("button", { name: "Save job" })).toHaveLength(1);
    expect(
      within(section).getByRole("link", { name: "Apply on employer site" }),
    ).toHaveAttribute("href", "https://example.com/apply");

    fireEvent.click(
      within(section).getByRole("button", { name: "Mark as Applied" }),
    );

    await waitFor(() =>
      expect(updateApplicationStatus).toHaveBeenCalledWith("app-1", "applied"),
    );
    expect(saveJob).toHaveBeenCalledWith("job-1");
    expect(
      await within(section).findByRole("link", { name: "View Application" }),
    ).toHaveAttribute("href", "/applications/app-1");
  });

  it("links a saved job into Application Tracking", async () => {
    saveJob.mockResolvedValue({ id: "app-9", status: "saved", job: JOB });

    renderFocused();

    await screen.findByRole("heading", {
      name: "Understand this job, then decide",
    });
    fireEvent.click(screen.getByRole("button", { name: "Save job" }));

    expect(
      await screen.findByRole("link", { name: "View in Tracking" }),
    ).toHaveAttribute("href", "/applications/app-9");
    expect(updateApplicationStatus).not.toHaveBeenCalled();
    expect(
      within(workflowPanel()).getByText("Saved · not applied yet"),
    ).toBeInTheDocument();
  });
});
