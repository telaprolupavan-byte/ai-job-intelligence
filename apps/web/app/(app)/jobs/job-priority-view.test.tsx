// @vitest-environment jsdom
//
// AJI-025 — the Jobs page's Priority view: opt-in (the listing stays the
// default), pinned to the ResumeVersion the selector shows, scoped by the
// same filters, refreshed on return from a job, and opening a job still
// lands on the unchanged AJI-023 workflow.
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
const getLatestJobResults = vi.fn();

vi.mock("@/lib/jobs", () => ({
  getJobs: (...args: unknown[]) => getJobs(...args),
  getJob: (...args: unknown[]) => getJob(...args),
  getLatestJobResults: (...args: unknown[]) => getLatestJobResults(...args),
  generateJobIntelligence: () => new Promise(() => {}),
  getJobEligibility: () => new Promise(() => {}),
  calculateJobMatch: vi.fn(),
  calculateAtsAlignment: vi.fn(),
  calculateGapAnalysis: vi.fn(),
  createResumeImprovement: vi.fn(),
  runResumeImprovementRecheck: vi.fn(),
}));

const getJobPriority = vi.fn();

vi.mock("@/lib/job-priority", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/job-priority")>()),
  getJobPriority: (...args: unknown[]) => getJobPriority(...args),
}));

vi.mock("@/lib/job-discovery", () => ({
  getDiscoveryStatus: () =>
    Promise.resolve({ source_configured: true, test_mode: false, last_run: null }),
}));

let resumes: unknown[] = [];

vi.mock("@/lib/resumes", () => ({
  getResumes: async () => resumes,
  getResumeVersions: async () => [
    { id: "version-1", name: "Master", is_master: true, created_at: "2026-01-01T00:00:00Z" },
    { id: "version-2", name: "Tailored", is_master: false, created_at: "2026-01-02T00:00:00Z" },
  ],
}));

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
  title: "Staff Data Engineer",
  company: "Acme",
  location: "Remote",
  country: "USA",
  remote_type: "remote",
  employment_type: "contract",
  salary_min: null,
  salary_max: null,
  salary_currency: null,
  contract_duration: null,
  contract_worker_type: null,
  description: "Build pipelines.",
  requirements: "Python",
  responsibilities: "Ship.",
  posting_date: null,
  source: "greenhouse",
  origin: "discovered",
  is_test_data: false,
  source_url: null,
  application_url: null,
  first_seen_at: "2026-01-01T00:00:00Z",
  last_seen_at: "2026-01-01T00:00:00Z",
};

function priorityResponse(resumeVersionId = "version-1") {
  return {
    engine_version: "1.0.0",
    ordering: ["hard_eligibility", "job_match_score", "ats_alignment_score", "posting_date", "job_id"],
    generated_at: "2026-09-23T00:00:00+00:00",
    user_id: "user-1",
    resume_version: {
      id: resumeVersionId,
      name: resumeVersionId === "version-1" ? "Master" : "Tailored",
      resume_filename: "cv.pdf",
      is_master: resumeVersionId === "version-1",
    },
    counts: { ranked: 1, partial: 0, not_ready: 0, excluded: 0, unanalyzed: 3 },
    items: [
      {
        job: JOB,
        rank: 1,
        state: "ranked",
        eligibility_status: "eligible",
        reasons: [
          { code: "job_match_score", source: "job_match", kind: "evidence", message: "Job Match 64%." },
        ],
        blocking_factors: [],
        inputs: {
          eligibility: { status: "eligible", engine_version: "1.0.0", failed_constraints: [], unknown_constraints: [] },
          job_match: {
            id: "m1", score: 64, confidence: "medium", engine_version: "1.0.0",
            job_intelligence_id: "ji", current: true, created_at: "2026-09-22T00:00:00",
          },
          ats_alignment: {
            id: "a1", overall_score: 58, confidence: "medium", must_have_matched: 2,
            must_have_total: 4, engine_version: "2.0.0", requirement_intelligence_id: "ri",
            current: true, created_at: "2026-09-22T00:00:00",
          },
        },
      },
    ],
    pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  searchParams = new URLSearchParams();
  resumes = [{ id: "resume-1", filename: "cv.pdf", created_at: "2026-01-01T00:00:00Z" }];

  getJobs.mockResolvedValue({
    jobs: [{ ...JOB, id: "listing-job", title: "Listing Only Job" }],
    pagination: { page: 1, page_size: 20, total: 1, total_pages: 1 },
  });
  getJobPriority.mockImplementation(async (params: { resumeVersionId?: string }) =>
    priorityResponse(params.resumeVersionId),
  );
  getJob.mockResolvedValue(JOB);
  getLatestJobResults.mockResolvedValue({
    match: null,
    ats: null,
    gapAnalysis: null,
    improvement: null,
  });
});

afterEach(() => {
  cleanup();
});

async function openPriorityView() {
  render(<JobsPage />);
  await screen.findByText("Listing Only Job");
  fireEvent.click(screen.getByRole("button", { name: "Priority order" }));
  return screen.findByRole("article", { name: "Staff Data Engineer" });
}

describe("Jobs page — Priority view (AJI-025)", () => {
  it("keeps the existing listing as the default and fetches nothing extra", async () => {
    render(<JobsPage />);

    expect(await screen.findByText("Listing Only Job")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "All jobs" })).toHaveAttribute("aria-pressed", "true");
    expect(getJobPriority).not.toHaveBeenCalled();
  });

  it("shows prioritized jobs pinned to the resume version the selector shows", async () => {
    const article = await openPriorityView();

    expect(getJobPriority).toHaveBeenCalledWith(
      expect.objectContaining({ resumeVersionId: "version-1", page: 1 }),
    );
    expect(article).toHaveTextContent("Priority 1 of 1");
    expect(screen.getByLabelText("Job Match: 64%")).toBeInTheDocument();
    expect(screen.getByLabelText("ATS Alignment: 58%")).toBeInTheDocument();
    expect(screen.getByText("Master (cv.pdf)")).toBeInTheDocument();
    // The listing's cards are not rendered in this view.
    expect(screen.queryByText("Listing Only Job")).not.toBeInTheDocument();
    expect(replace).toHaveBeenLastCalledWith("/jobs?view=priority", { scroll: false });
  });

  it("re-orders for a newly selected resume version", async () => {
    await openPriorityView();

    fireEvent.click(screen.getByRole("button", { name: "pick version 2" }));

    await waitFor(() =>
      expect(getJobPriority).toHaveBeenLastCalledWith(
        expect.objectContaining({ resumeVersionId: "version-2" }),
      ),
    );
    expect(await screen.findByText("Tailored (cv.pdf)")).toBeInTheDocument();
  });

  it("applies the listing filters to the priority order", async () => {
    await openPriorityView();

    fireEvent.change(screen.getByLabelText("Employment Type"), {
      target: { value: "contract" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Search Jobs/ }));

    await waitFor(() =>
      expect(getJobPriority).toHaveBeenLastCalledWith(
        expect.objectContaining({ employment_type: "contract", page: 1 }),
      ),
    );
  });

  it("opens the unchanged job workflow and refreshes priority on return", async () => {
    await openPriorityView();
    const callsBefore = getJobPriority.mock.calls.length;

    fireEvent.click(
      screen.getByRole("button", { name: "Open job workflow for Staff Data Engineer" }),
    );

    expect(await screen.findByText("Understand this job, then decide")).toBeInTheDocument();
    expect(getJob).toHaveBeenCalledWith("job-1");
    for (const stage of [
      "Job Intelligence",
      "Hard Eligibility",
      "Job Match",
      "ATS Alignment",
      "Gap Analysis",
      "Resume Improvement",
      "Application Tracking",
    ]) {
      expect(screen.getAllByText(stage).length).toBeGreaterThan(0);
    }

    fireEvent.click(screen.getByRole("button", { name: "← All jobs" }));

    await screen.findByRole("article", { name: "Staff Data Engineer" });
    expect(getJobPriority.mock.calls.length).toBeGreaterThan(callsBefore);
  });

  it("asks for a resume instead of ranking when there is none", async () => {
    resumes = [];
    render(<JobsPage />);
    await screen.findByText("Listing Only Job");

    fireEvent.click(screen.getByRole("button", { name: "Priority order" }));

    expect(await screen.findByText("Upload a resume to prioritize jobs")).toBeInTheDocument();
    expect(getJobPriority).not.toHaveBeenCalled();
  });

  it("shows an error with a working retry", async () => {
    getJobPriority.mockRejectedValueOnce(new Error("Priority is down."));
    render(<JobsPage />);
    await screen.findByText("Listing Only Job");

    fireEvent.click(screen.getByRole("button", { name: "Priority order" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Priority is down.");
    fireEvent.click(screen.getByRole("button", { name: "Try Again" }));

    expect(await screen.findByRole("article", { name: "Staff Data Engineer" })).toBeInTheDocument();
  });

  it("restores the Priority view from the URL", async () => {
    searchParams = new URLSearchParams("view=priority");
    render(<JobsPage />);

    expect(await screen.findByRole("article", { name: "Staff Data Engineer" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Priority order" })).toHaveAttribute("aria-pressed", "true");
  });

  it("switches back to the unchanged listing", async () => {
    await openPriorityView();

    fireEvent.click(screen.getByRole("button", { name: "All jobs" }));

    expect(await screen.findByText("Listing Only Job")).toBeInTheDocument();
    expect(screen.queryByRole("article", { name: "Staff Data Engineer" })).not.toBeInTheDocument();
  });
});
