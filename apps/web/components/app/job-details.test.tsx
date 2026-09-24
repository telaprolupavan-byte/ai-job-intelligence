// @vitest-environment jsdom
//
// AJI-023 (Job Search) — the opened job's details: every field the source
// provided, in full, and "Not stated" (never a guess) for the rest.
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import "@testing-library/jest-dom/vitest";

import type { Job } from "@/lib/jobs";
import JobDetails from "./job-details";

const LONG_DESCRIPTION = [
  "Design and operate Python services that power a job search product.",
  "You will own APIs end to end, from schema to on-call.",
  "Line three of a description the listing card would clamp.",
  "Line four, which must still be visible on the opened job.",
].join("\n");

function job(overrides: Partial<Job> = {}): Job {
  return {
    id: "job-1",
    title: "Senior Backend Engineer",
    company: "Initech",
    location: "Austin, TX",
    country: "USA",
    remote_type: "hybrid",
    employment_type: "full_time",
    salary_min: 120000,
    salary_max: 150000,
    salary_currency: "USD",
    contract_duration: null,
    contract_worker_type: null,
    description: LONG_DESCRIPTION,
    requirements: "5+ years of Python\nPostgreSQL",
    responsibilities: "Build APIs\nReview code",
    posting_date: "2026-09-01T09:00:00",
    source: "greenhouse",
    source_job_id: "4567",
    origin: "discovered",
    is_test_data: false,
    source_url: "https://boards.example/jobs/4567",
    application_url: null,
    first_seen_at: "2026-09-02T00:00:00",
    last_seen_at: "2026-09-02T00:00:00",
    ...overrides,
  };
}

function fact(label: string): HTMLElement {
  const term = screen.getByText(label, { selector: "dt" });
  return term.nextElementSibling as HTMLElement;
}

describe("JobDetails (AJI-023 Job Search)", () => {
  afterEach(() => cleanup());

  it("shows every provided field, with the full text", () => {
    render(<JobDetails job={job()} />);

    expect(fact("Company")).toHaveTextContent("Initech");
    expect(fact("Location")).toHaveTextContent("Austin, TX");
    expect(fact("Work arrangement")).toHaveTextContent("Hybrid");
    expect(fact("Employment type")).toHaveTextContent("Full-Time");
    expect(fact("Compensation")).toHaveTextContent("USD 120,000 – 150,000");
    expect(fact("Posted")).toHaveTextContent("Sep 1, 2026");
    expect(fact("Source job ID")).toHaveTextContent("4567");

    const region = screen.getByRole("region", { name: "Job details" });
    expect(
      within(region).getByText(/Line four, which must still be visible/),
    ).toBeInTheDocument();
    expect(within(region).getByText("Requirements")).toBeInTheDocument();
    expect(within(region).getByText(/5\+ years of Python/)).toBeInTheDocument();
    expect(within(region).getByText("Responsibilities")).toBeInTheDocument();

    // Contract-only facts are not applicable to a full-time role.
    expect(screen.queryByText("Contract length")).not.toBeInTheDocument();
  });

  it("flags synthetic development data so it never reads as a real posting (AJI-030)", () => {
    render(
      <JobDetails
        job={job({
          is_test_data: true,
          source: "nero_development_dataset",
          source_url: null,
          expires_at: "2026-10-22T00:00:00",
        })}
      />,
    );

    const region = screen.getByRole("region", { name: "Job details" });
    expect(within(region).getByRole("note")).toHaveTextContent(
      /Development data: this job is synthetic/,
    );
    expect(within(region).getByRole("note")).toHaveTextContent(
      /not a real posting/,
    );
    expect(fact("Closes")).toHaveTextContent("Oct 22, 2026");
  });

  it("shows no development-data note on a real job", () => {
    render(<JobDetails job={job()} />);

    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });

  it("marks missing facts as Not stated and never fabricates them", () => {
    render(
      <JobDetails
        job={job({
          company: null,
          location: null,
          remote_type: null,
          employment_type: null,
          salary_min: null,
          salary_max: null,
          salary_currency: null,
          posting_date: null,
          source_job_id: null,
          description: null,
          requirements: null,
          responsibilities: null,
        })}
      />,
    );

    for (const label of [
      "Company",
      "Location",
      "Work arrangement",
      "Employment type",
      "Compensation",
      "Posted",
    ]) {
      expect(fact(label)).toHaveTextContent("Not stated");
    }

    expect(screen.queryByText("Source job ID")).not.toBeInTheDocument();
    expect(screen.queryByText("Requirements")).not.toBeInTheDocument();
    expect(
      screen.getByText("The source didn't provide a description for this job."),
    ).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("USD");
  });

  it("shows a salary without a currency the source did not state", () => {
    render(<JobDetails job={job({ salary_currency: null })} />);

    expect(fact("Compensation")).toHaveTextContent(/^120,000 – 150,000$/);
  });

  it("shows contract details on a contract role", () => {
    render(
      <JobDetails
        job={job({
          employment_type: "contract",
          contract_duration: "6 months",
          contract_worker_type: "w2",
        })}
      />,
    );

    expect(fact("Employment type")).toHaveTextContent("Contract · 6 months");
    expect(fact("Contract length")).toHaveTextContent("6 months");
    expect(fact("Worker type")).toHaveTextContent("W2");
  });

  it("formats multi-word worker types readably", () => {
    render(
      <JobDetails
        job={job({
          employment_type: "contract",
          contract_worker_type: "corp_to_corp",
        })}
      />,
    );

    expect(fact("Worker type")).toHaveTextContent("Corp To Corp");
  });

  it("marks unknown contract details on a contract role", () => {
    render(<JobDetails job={job({ employment_type: "contract" })} />);

    expect(fact("Contract length")).toHaveTextContent("Not stated");
    expect(fact("Worker type")).toHaveTextContent("Not stated");
  });

  // AJI-028: provider-stated expiry.
  it("shows the closing date only when the provider stated one", () => {
    render(<JobDetails job={job({ expires_at: "2026-12-31T22:00:00" })} />);

    expect(fact("Closes")).toHaveTextContent("Dec 31, 2026");
  });

  it("omits the closing date when none was stated (never 'Not stated')", () => {
    render(<JobDetails job={job({ expires_at: null })} />);

    expect(screen.queryByText("Closes")).not.toBeInTheDocument();
  });

  it("omits the closing date for responses from an older API", () => {
    render(<JobDetails job={job()} />);

    expect(screen.queryByText("Closes")).not.toBeInTheDocument();
  });
});
