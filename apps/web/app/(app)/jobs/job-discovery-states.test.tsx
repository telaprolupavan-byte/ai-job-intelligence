// @vitest-environment jsdom
//
// AJI-024 — Jobs page discovery states: discovered vs. user-submitted jobs,
// Full-Time vs. Contract distinction, test-fixture labelling, the "no
// source connected" empty state, a failed latest run, and a list error.
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace }),
  usePathname: () => "/jobs",
  useSearchParams: () => new URLSearchParams(),
}));

const getJobs = vi.fn();

vi.mock("@/lib/jobs", () => ({
  getJobs: (...args: unknown[]) => getJobs(...args),
  getJob: vi.fn(),
  generateJobIntelligence: vi.fn(),
  calculateJobMatch: vi.fn(),
  calculateAtsAlignment: vi.fn(),
  calculateGapAnalysis: vi.fn(),
  getJobEligibility: vi.fn(),
  getLatestJobResults: vi.fn(),
  createResumeImprovement: vi.fn(),
  runResumeImprovementRecheck: vi.fn(),
}));

const getDiscoveryStatus = vi.fn();

vi.mock("@/lib/job-discovery", () => ({
  getDiscoveryStatus: (...args: unknown[]) => getDiscoveryStatus(...args),
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

function makeJob(overrides: Record<string, unknown>) {
  return {
    id: "job",
    title: "Engineer",
    company: "Example Inc",
    location: null,
    country: "USA",
    remote_type: null,
    employment_type: null,
    salary_min: null,
    salary_max: null,
    salary_currency: null,
    contract_duration: null,
    contract_worker_type: null,
    description: "Build things.",
    requirements: null,
    responsibilities: null,
    posting_date: null,
    source: "greenhouse",
    origin: "discovered",
    is_test_data: false,
    source_url: null,
    application_url: null,
    first_seen_at: "2026-09-22T00:00:00",
    last_seen_at: "2026-09-22T00:00:00",
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

const CONFIGURED = {
  source_configured: true,
  test_mode: false,
  last_run: { status: "succeeded", completed_at: "2026-09-22T00:00:00" },
};

describe("Jobs page — discovery states (AJI-024)", () => {
  beforeEach(() => {
    getJobs.mockReset();
    getDiscoveryStatus.mockReset().mockResolvedValue(CONFIGURED);
  });

  afterEach(() => {
    cleanup();
  });

  it("distinguishes discovered jobs from the user's own private jobs", async () => {
    getJobs.mockResolvedValue(
      jobsResponse([
        makeJob({ id: "d1", title: "Discovered Role" }),
        makeJob({
          id: "u1",
          title: "My Pasted Role",
          source: "user_submitted",
          origin: "user_submitted",
        }),
      ]),
    );

    render(<JobsPage />);

    expect(await screen.findByText("Discovered Role")).toBeInTheDocument();
    expect(screen.getByText("Discovered · Greenhouse")).toBeInTheDocument();
    expect(screen.getByText("Added by you · private")).toBeInTheDocument();
    expect(screen.queryByText("user_submitted")).not.toBeInTheDocument();
  });

  it("keeps Full-Time and Contract jobs visibly distinct", async () => {
    getJobs.mockResolvedValue(
      jobsResponse([
        makeJob({ id: "f", title: "FT Role", employment_type: "full_time" }),
        makeJob({
          id: "c",
          title: "Contract Role",
          employment_type: "contract",
          contract_duration: "6 months",
        }),
      ]),
    );

    render(<JobsPage />);

    const fullTime = await screen.findByText("Full-Time");
    const contract = screen.getByText("Contract · 6 months");

    expect(fullTime.className).not.toEqual(contract.className);
  });

  it("labels test-fixture jobs and shows the test-mode banner", async () => {
    getDiscoveryStatus.mockResolvedValue({ ...CONFIGURED, test_mode: true });
    getJobs.mockResolvedValue(
      jobsResponse([
        makeJob({
          id: "t1",
          title: "Fixture Role",
          source: "nero_test_fixture",
          is_test_data: true,
        }),
      ]),
    );

    render(<JobsPage />);

    expect(await screen.findByText("Fixture Role")).toBeInTheDocument();
    expect(await screen.findByRole("note")).toHaveTextContent(
      /not real\s+postings/,
    );
    // Banner chip + card chip.
    expect(screen.getAllByText("Test data")).toHaveLength(2);
    expect(screen.getByText("Discovered · test fixture")).toBeInTheDocument();
  });

  it("does not show the test-mode banner for production data", async () => {
    getJobs.mockResolvedValue(
      jobsResponse([makeJob({ id: "p1", title: "Prod Role" })]),
    );

    render(<JobsPage />);

    expect(await screen.findByText("Prod Role")).toBeInTheDocument();
    expect(screen.queryByText("Test data")).not.toBeInTheDocument();
  });

  it("explains when no discovery source is connected", async () => {
    getDiscoveryStatus.mockResolvedValue({
      source_configured: false,
      test_mode: false,
      last_run: null,
    });
    getJobs.mockResolvedValue(jobsResponse([]));

    render(<JobsPage />);

    expect(
      await screen.findByText("No job source connected yet"),
    ).toBeInTheDocument();
    expect(screen.queryByText("No jobs found")).not.toBeInTheDocument();
    const addLinks = screen.getAllByRole("link", { name: "Add a job" });
    expect(addLinks.length).toBeGreaterThanOrEqual(2);
  });

  it("keeps the generic empty state when a source is configured", async () => {
    getJobs.mockResolvedValue(jobsResponse([]));

    render(<JobsPage />);

    expect(await screen.findByText("No jobs found")).toBeInTheDocument();
    expect(
      screen.queryByText("No job source connected yet"),
    ).not.toBeInTheDocument();
  });

  it("notes a failed latest discovery run without hiding existing jobs", async () => {
    getDiscoveryStatus.mockResolvedValue({
      ...CONFIGURED,
      last_run: { status: "failed", completed_at: "2026-09-22T00:00:00" },
    });
    getJobs.mockResolvedValue(
      jobsResponse([makeJob({ id: "e1", title: "Earlier Role" })]),
    );

    render(<JobsPage />);

    expect(await screen.findByText("Earlier Role")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByText(/most recent job discovery run did not complete/),
      ).toBeInTheDocument(),
    );
  });

  it("shows the discovery error state when jobs cannot load", async () => {
    getJobs.mockRejectedValue(new Error("boom"));
    vi.spyOn(console, "error").mockImplementation(() => {});

    render(<JobsPage />);

    expect(await screen.findByText("Discovery Error")).toBeInTheDocument();
  });

  it("renders normally when the status endpoint is unavailable", async () => {
    getDiscoveryStatus.mockRejectedValue(new Error("status down"));
    getJobs.mockResolvedValue(
      jobsResponse([makeJob({ id: "s1", title: "Still Listed" })]),
    );

    render(<JobsPage />);

    expect(await screen.findByText("Still Listed")).toBeInTheDocument();
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });
});
