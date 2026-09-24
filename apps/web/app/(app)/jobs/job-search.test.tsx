// @vitest-environment jsdom
//
// AJI-023 (Job Search) — the Jobs page search flow: enter criteria,
// search, see results, recover from failures, open a job and read its
// details.
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

vi.mock("@/lib/jobs", () => ({
  getJobs: (...args: unknown[]) => getJobs(...args),
  getJob: (...args: unknown[]) => getJob(...args),
  generateJobIntelligence: () => new Promise(() => {}),
  calculateJobMatch: vi.fn(),
  calculateAtsAlignment: vi.fn(),
  calculateGapAnalysis: vi.fn(),
  getJobEligibility: vi.fn(),
  getLatestJobResults: vi.fn(),
  createResumeImprovement: vi.fn(),
  runResumeImprovementRecheck: vi.fn(),
}));

vi.mock("@/lib/job-discovery", () => ({
  getDiscoveryStatus: () =>
    Promise.resolve({
      source_configured: true,
      test_mode: false,
      last_run: null,
    }),
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

function makeJob(overrides: Record<string, unknown> = {}) {
  return {
    id: "job-1",
    title: "Platform Engineer",
    company: "Initech",
    location: "Austin, TX",
    country: "USA",
    remote_type: "hybrid",
    employment_type: "full_time",
    salary_min: null,
    salary_max: null,
    salary_currency: null,
    contract_duration: null,
    contract_worker_type: null,
    description: "Run the platform.",
    requirements: null,
    responsibilities: null,
    posting_date: "2026-09-01T09:00:00",
    source: "greenhouse",
    source_job_id: "123",
    origin: "discovered",
    is_test_data: false,
    source_url: null,
    application_url: null,
    first_seen_at: "2026-09-02T00:00:00",
    last_seen_at: "2026-09-02T00:00:00",
    ...overrides,
  };
}

function jobsResponse(jobs: unknown[]) {
  return {
    jobs,
    pagination: {
      page: 1,
      page_size: 20,
      total: jobs.length,
      total_pages: jobs.length ? 1 : 0,
    },
  };
}

function searchFor(keyword: string) {
  fireEvent.change(screen.getByLabelText("Role / Keyword"), {
    target: { value: keyword },
  });
  fireEvent.click(screen.getByRole("button", { name: /Search Jobs/ }));
}

describe("Jobs page — search flow (AJI-023 Job Search)", () => {
  beforeEach(() => {
    searchParams = new URLSearchParams();
    replace.mockReset();
    getJob.mockReset();
    getJobs.mockReset().mockResolvedValue(jobsResponse([makeJob()]));
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    cleanup();
  });

  it("searches with the entered criteria, cleaned, from page 1", async () => {
    render(<JobsPage />);
    expect(await screen.findByText("Platform Engineer")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Employment Type"), {
      target: { value: "contract" },
    });
    fireEvent.change(screen.getByLabelText("Work Arrangement"), {
      target: { value: "remote" },
    });
    fireEvent.change(screen.getByLabelText("Location"), {
      target: { value: "  New   York " },
    });
    searchFor("   data   engineer  ");

    await waitFor(() =>
      expect(getJobs).toHaveBeenLastCalledWith({
        search: "data engineer",
        employment_type: "contract",
        remote_type: "remote",
        location: "New York",
        page: 1,
        page_size: 20,
      }),
    );
    // The form shows exactly what was searched for.
    expect(screen.getByLabelText("Role / Keyword")).toHaveValue(
      "data engineer",
    );
    await waitFor(() =>
      expect(replace).toHaveBeenLastCalledWith(
        "/jobs?search=data+engineer&employment_type=contract&remote_type=remote&location=New+York",
        { scroll: false },
      ),
    );
  });

  it("sends no keyword for a blank search", async () => {
    render(<JobsPage />);
    await screen.findByText("Platform Engineer");
    getJobs.mockClear();

    searchFor("    ");

    await waitFor(() => expect(getJobs).toHaveBeenCalled());
    expect(getJobs.mock.lastCall?.[0]).toMatchObject({ search: undefined });
  });

  it("limits free-text criteria to what the API accepts", async () => {
    render(<JobsPage />);
    await screen.findByText("Platform Engineer");

    expect(screen.getByLabelText("Role / Keyword")).toHaveAttribute(
      "maxLength",
      "200",
    );
    expect(screen.getByLabelText("Location")).toHaveAttribute(
      "maxLength",
      "200",
    );
  });

  it("ignores a filter value from the URL that the API would reject", async () => {
    searchParams = new URLSearchParams(
      "employment_type=Full-Time&remote_type=remote&search=ml",
    );

    render(<JobsPage />);

    await waitFor(() =>
      expect(getJobs).toHaveBeenCalledWith(
        expect.objectContaining({
          search: "ml",
          employment_type: undefined,
          remote_type: "remote",
        }),
      ),
    );
    expect(screen.getByLabelText("Employment Type")).toHaveValue("");
  });

  it("shows the result details on each job card", async () => {
    render(<JobsPage />);

    const card = (await screen.findByText("Platform Engineer")).closest(
      "article",
    ) as HTMLElement;

    expect(within(card).getByText("Initech")).toBeInTheDocument();
    expect(within(card).getByText("Austin, TX")).toBeInTheDocument();
    expect(within(card).getByText("Hybrid")).toBeInTheDocument();
    expect(within(card).getByText("Full-Time")).toBeInTheDocument();
    expect(within(card).getByText("Discovered · Greenhouse")).toBeInTheDocument();
    expect(within(card).getByText("Sep 1, 2026")).toBeInTheDocument();
    // No salary was stated, so none is shown (and no currency invented).
    expect(within(card).queryByText("Compensation")).not.toBeInTheDocument();
    expect(screen.getByText(/^1 result ·/)).toBeInTheDocument();
  });

  it("omits the posted date when the source gave none", async () => {
    getJobs.mockResolvedValue(jobsResponse([makeJob({ posting_date: null })]));

    render(<JobsPage />);

    await screen.findByText("Platform Engineer");
    expect(screen.queryByText("Posted")).not.toBeInTheDocument();
  });

  it("shows the empty state for a search with no matches", async () => {
    render(<JobsPage />);
    await screen.findByText("Platform Engineer");

    getJobs.mockResolvedValue(jobsResponse([]));
    searchFor("nothing matches this");

    expect(await screen.findByText("No jobs found")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Clear Filters" }),
    ).toBeInTheDocument();
  });

  it("never leaves the previous results under an error, and retries", async () => {
    render(<JobsPage />);
    expect(await screen.findByText("Platform Engineer")).toBeInTheDocument();

    getJobs.mockRejectedValueOnce(new ApiError("Service unavailable", 503));
    searchFor("data engineer");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Unable to load jobs. Please try again.");
    expect(screen.queryByText("Platform Engineer")).not.toBeInTheDocument();
    expect(screen.queryByText(/results? ·/)).not.toBeInTheDocument();

    getJobs.mockResolvedValueOnce(
      jobsResponse([makeJob({ id: "job-2", title: "Data Engineer" })]),
    );
    fireEvent.click(within(alert).getByRole("button", { name: "Try Again" }));

    expect(await screen.findByText("Data Engineer")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(getJobs.mock.lastCall?.[0]).toMatchObject({
      search: "data engineer",
    });
  });

  it("explains rejected criteria without offering a pointless retry", async () => {
    getJobs.mockRejectedValue(new ApiError("Something went wrong.", 422));

    render(<JobsPage />);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "Some search criteria weren't accepted. Check them and search again.",
    );
    expect(
      within(alert).queryByRole("button", { name: "Try Again" }),
    ).not.toBeInTheDocument();
  });

  it("opens a job from the results and shows its full details", async () => {
    const detail = {
      ...makeJob({
        description: "Run the platform.\nFourth line kept in full.",
        requirements: "Kubernetes\nGo",
        salary_min: 140000,
        salary_max: 170000,
        salary_currency: null,
      }),
      raw_submitted_content: null,
    };
    getJob.mockResolvedValue(detail);

    render(<JobsPage />);
    fireEvent.click(
      await screen.findByRole("button", {
        name: "Open job workflow for Platform Engineer",
      }),
    );

    const details = await screen.findByRole("region", { name: "Job details" });
    expect(getJob).toHaveBeenCalledWith("job-1");
    expect(
      within(details).getByText(/Fourth line kept in full\./),
    ).toBeInTheDocument();
    expect(within(details).getByText(/Kubernetes/)).toBeInTheDocument();
    expect(within(details).getByText("140,000 – 170,000")).toBeInTheDocument();
    expect(within(details).getByText("Sep 1, 2026")).toBeInTheDocument();
    expect(within(details).getByText("123")).toBeInTheDocument();
    // The search form gives way to the opened job, with a way back.
    expect(screen.queryByText("Search Parameters")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "← All jobs" }),
    ).toBeInTheDocument();
  });
});
