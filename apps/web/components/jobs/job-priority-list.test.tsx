// @vitest-environment jsdom
//
// AJI-025 — the Priority view component: states, explanations, Match and
// ATS shown separately (never combined), private/test/Full-Time/Contract
// labelling, and layout classes that keep it inside a phone viewport.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";

import JobPriorityList from "./job-priority-list";
import type {
  JobPriorityItem,
  JobPriorityResponse,
} from "@/lib/job-priority";

afterEach(() => {
  cleanup();
});

function job(id: string, overrides: Record<string, unknown> = {}) {
  return {
    id,
    title: `Job ${id}`,
    company: "Example Inc",
    location: "Remote",
    country: "USA",
    remote_type: "remote",
    employment_type: "full_time",
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
  } as JobPriorityItem["job"];
}

function item(
  id: string,
  overrides: Partial<JobPriorityItem> = {},
  jobOverrides: Record<string, unknown> = {},
): JobPriorityItem {
  return {
    job: job(id, jobOverrides),
    rank: 1,
    state: "ranked",
    eligibility_status: "eligible",
    reasons: [
      {
        code: "eligibility_eligible",
        source: "eligibility",
        kind: "evidence",
        message: "Hard Eligibility: eligible - none of your configured hard requirements rule this job out.",
      },
      { code: "job_match_score", source: "job_match", kind: "evidence", message: "Job Match 82%." },
      { code: "ats_score", source: "ats_alignment", kind: "evidence", message: "ATS Alignment 71%." },
    ],
    blocking_factors: [],
    inputs: {
      eligibility: {
        status: "eligible",
        engine_version: "1.0.0",
        failed_constraints: [],
        unknown_constraints: [],
      },
      job_match: {
        id: `m-${id}`,
        score: 82,
        confidence: "medium",
        engine_version: "1.0.0",
        job_intelligence_id: "ji",
        current: true,
        created_at: "2026-09-22T00:00:00",
      },
      ats_alignment: {
        id: `a-${id}`,
        overall_score: 71,
        confidence: "medium",
        must_have_matched: 3,
        must_have_total: 4,
        engine_version: "2.0.0",
        requirement_intelligence_id: "ri",
        current: true,
        created_at: "2026-09-22T00:00:00",
      },
    },
    ...overrides,
  };
}

function response(
  items: JobPriorityItem[],
  overrides: Partial<JobPriorityResponse> = {},
): JobPriorityResponse {
  const count = (state: string) => items.filter((i) => i.state === state).length;
  return {
    engine_version: "1.0.0",
    ordering: ["hard_eligibility", "job_match_score", "ats_alignment_score", "posting_date", "job_id"],
    generated_at: "2026-09-23T00:00:00+00:00",
    user_id: "user-1",
    resume_version: {
      id: "version-1",
      name: "Master Resume",
      resume_filename: "cv.pdf",
      is_master: true,
    },
    counts: {
      ranked: count("ranked"),
      partial: count("partial"),
      not_ready: count("not_ready"),
      excluded: count("excluded"),
      unanalyzed: 0,
    },
    items,
    pagination: { page: 1, page_size: 20, total: items.length, total_pages: 1 },
    ...overrides,
  };
}

function renderList(
  result: JobPriorityResponse | null,
  props: Partial<React.ComponentProps<typeof JobPriorityList>> = {},
) {
  const handlers = {
    onRetry: vi.fn(),
    onOpenJob: vi.fn(),
    onPageChange: vi.fn(),
  };
  render(
    <JobPriorityList status="ready" result={result} {...handlers} {...props} />,
  );
  return handlers;
}

function card(title: string) {
  return screen.getByRole("article", { name: title });
}

describe("JobPriorityList (AJI-025)", () => {
  it("renders ranked jobs in the server's order with their position", () => {
    renderList(
      response([
        item("a", { rank: 1 }),
        item("b", { rank: 2, state: "partial" }),
      ]),
    );

    const ranked = screen.getByRole("list", { name: "Ranked jobs" });
    const titles = within(ranked).getAllByRole("heading", { level: 4 });
    expect(titles.map((h) => h.textContent)).toEqual(["Job a", "Job b"]);

    expect(within(card("Job a")).getByText("Priority 1 of 2 ranked")).toBeInTheDocument();
    expect(within(card("Job b")).getByText("Priority 2 of 2 ranked")).toBeInTheDocument();
    expect(within(card("Job a")).getByText("Ranked")).toBeInTheDocument();
    expect(within(card("Job b")).getByText("Ranked · partial evidence")).toBeInTheDocument();
  });

  it("shows Job Match and ATS Alignment separately, never combined", () => {
    renderList(response([item("a")]));

    const article = card("Job a");
    expect(within(article).getByLabelText("Job Match: 82%")).toBeInTheDocument();
    expect(within(article).getByLabelText("ATS Alignment: 71%")).toBeInTheDocument();
    // No blended value such as their average (77%) or sum is shown.
    expect(article.textContent).not.toMatch(/77%|153/);
    expect(article.textContent?.toLowerCase()).not.toContain("priority score");
  });

  it("explains a ranked job from its own evidence", () => {
    renderList(response([item("a")]));

    const article = card("Job a");
    expect(within(article).getByText("Based on")).toBeInTheDocument();
    expect(within(article).getByText("Job Match 82%.")).toBeInTheDocument();
    expect(within(article).getByText("ATS Alignment 71%.")).toBeInTheDocument();
  });

  it("marks missing and out-of-date analyses instead of inventing values", () => {
    renderList(
      response([
        item("a", {
          state: "partial",
          reasons: [
            {
              code: "ats_missing",
              source: "ats_alignment",
              kind: "caution",
              message: "ATS Alignment has not been calculated for this resume version.",
            },
            {
              code: "job_match_outdated_job_intelligence",
              source: "job_match",
              kind: "caution",
              message: "Job Match was calculated from an earlier Job Intelligence snapshot of this job; recalculate it to refresh.",
            },
          ],
          inputs: {
            ...item("a").inputs,
            job_match: { ...item("a").inputs.job_match!, current: false },
            ats_alignment: null,
          },
        }),
      ]),
    );

    const article = card("Job a");
    expect(within(article).getByLabelText("ATS Alignment: not calculated")).toBeInTheDocument();
    expect(within(article).getByText("Not calculated")).toBeInTheDocument();
    expect(within(article).getByText("Out of date")).toBeInTheDocument();
    expect(within(article).getByText("Keep in mind")).toBeInTheDocument();
    expect(
      within(article).getByText("ATS Alignment has not been calculated for this resume version."),
    ).toBeInTheDocument();
  });

  it("keeps unknown eligibility visibly unknown", () => {
    renderList(
      response([
        item("a", {
          eligibility_status: "unknown",
          reasons: [
            {
              code: "eligibility_unknown_check",
              source: "eligibility",
              kind: "caution",
              message: "Job does not disclose an employment type.",
            },
          ],
        }),
      ]),
    );

    const article = card("Job a");
    expect(within(article).getByText("Eligibility unknown")).toBeInTheDocument();
    expect(within(article).getByText("Job does not disclose an employment type.")).toBeInTheDocument();
  });

  it("lists not-ready jobs separately, unranked, with the reason", () => {
    renderList(
      response([
        item("a"),
        item("b", {
          rank: null,
          state: "not_ready",
          blocking_factors: [
            {
              code: "job_match_missing",
              source: "job_match",
              message: "Job Match has not been calculated for this resume version, so this job cannot be ordered by fit yet.",
            },
          ],
          inputs: { ...item("b").inputs, job_match: null },
        }),
      ]),
    );

    expect(screen.getByRole("heading", { name: "Not ranked yet" })).toBeInTheDocument();
    const article = card("Job b");
    expect(within(article).queryByTestId("priority-position")).not.toBeInTheDocument();
    expect(within(article).getByText("Not ranked yet")).toBeInTheDocument();
    expect(within(article).getByText(/cannot be ordered by fit yet/)).toBeInTheDocument();
    // Only the one ranked job counts toward positions.
    expect(within(card("Job a")).getByText("Priority 1 of 1 ranked")).toBeInTheDocument();
  });

  it("shows excluded jobs with the failed requirement and no scores", () => {
    renderList(
      response([
        item("x", {
          rank: null,
          state: "excluded",
          eligibility_status: "ineligible",
          reasons: [],
          blocking_factors: [
            {
              code: "eligibility_failed",
              source: "eligibility",
              message: "Employment type 'contract' is not in your accepted list (full_time).",
            },
          ],
        }),
      ]),
    );

    expect(
      screen.getByRole("heading", { name: "Excluded by your hard requirements" }),
    ).toBeInTheDocument();
    const article = card("Job x");
    expect(within(article).getByText("Excluded")).toBeInTheDocument();
    expect(within(article).getByText("Ineligible")).toBeInTheDocument();
    expect(within(article).getByText("Ruled out by")).toBeInTheDocument();
    expect(within(article).getByText(/not in your accepted list/)).toBeInTheDocument();
    expect(within(article).queryByLabelText(/^Job Match:/)).not.toBeInTheDocument();
    expect(within(article).queryByTestId("priority-position")).not.toBeInTheDocument();
  });

  it("labels private, test-data, Full-Time and Contract jobs", () => {
    renderList(
      response([
        item("mine", {}, { origin: "user_submitted", source: "user_submitted" }),
        item("fixture", { rank: 2 }, { is_test_data: true, source: "nero_test_fixture" }),
        item("c", { rank: 3 }, { employment_type: "contract", contract_duration: "6 months" }),
      ]),
    );

    expect(within(card("Job mine")).getByText("Added by you · private")).toBeInTheDocument();
    expect(within(card("Job mine")).getByText("Full-Time")).toBeInTheDocument();
    expect(within(card("Job fixture")).getByText("Test data")).toBeInTheDocument();
    expect(within(card("Job c")).getByText("Contract · 6 months")).toBeInTheDocument();
  });

  it("opens a job's workflow", () => {
    const { onOpenJob } = renderList(response([item("a")]));

    fireEvent.click(screen.getByRole("button", { name: "Open job workflow for Job a" }));

    expect(onOpenJob).toHaveBeenCalledWith("a");
  });

  it("shows tracking status as context only", () => {
    renderList(response([item("a")]), {
      applicationStatusByJobId: { a: "applied" },
    });

    expect(within(card("Job a")).getByText("Tracking: Applied")).toBeInTheDocument();
  });

  it("says which resume version the order is for and what isn't included", () => {
    const result = response([item("a")]);
    result.counts.unanalyzed = 5;
    renderList(result);

    expect(screen.getByText("Master Resume (cv.pdf)")).toBeInTheDocument();
    expect(screen.getByText(/5 other jobs have/)).toBeInTheDocument();
    expect(screen.getByText(/doesn't predict interviews or offers/)).toBeInTheDocument();
    expect(document.body.textContent?.toLowerCase()).not.toMatch(/recommend/);
  });

  it("scopes a position to ranked jobs, not every job NERO knows about", () => {
    const result = response([
      item("a", { rank: 1 }),
      item("b", { rank: 2 }),
      item("n", { rank: null, state: "not_ready" }),
      item("x", { rank: null, state: "excluded", eligibility_status: "ineligible" }),
    ]);
    result.counts.unanalyzed = 6;
    renderList(result);

    expect(within(card("Job a")).getByText("Priority 1 of 2 ranked")).toBeInTheDocument();
    const summary = screen.getByLabelText("Priority summary");
    // 2 ranked + 1 not ready + 1 excluded + 6 not analyzed.
    expect(summary).toHaveTextContent("10 jobs in view");
    expect(summary).toHaveTextContent("2 ranked");
    expect(summary).toHaveTextContent("6 not analyzed");
    const explainer = document.getElementById("priority-explainer");
    expect(explainer).toHaveTextContent(
      "first among those 2 ranked jobs, not among every job NERO has found",
    );
  });

  it("states the unknown-eligibility and tracking-status rules it applies", () => {
    renderList(response([item("a")]));

    const explainer = document.getElementById("priority-explainer");
    expect(explainer).toHaveTextContent(
      "jobs confirmed eligible ahead of jobs whose eligibility is unknown",
    );
    expect(explainer).toHaveTextContent(
      "Your tracking status (saved, applied, rejected and so on) doesn't change the order",
    );
  });

  it("has an empty state when nothing is analyzed", () => {
    renderList(response([]));

    expect(screen.getByText("No analyzed jobs to prioritize yet")).toBeInTheDocument();
  });

  it("has loading, error and no-resume states", () => {
    const { onRetry } = renderList(null, { status: "error", error: "Boom." });
    expect(screen.getByRole("alert")).toHaveTextContent("Boom.");
    fireEvent.click(screen.getByRole("button", { name: "Try Again" }));
    expect(onRetry).toHaveBeenCalled();
    cleanup();

    renderList(null, { status: "loading" });
    expect(screen.getByRole("status")).toHaveTextContent("Ordering your analyzed jobs");
    cleanup();

    renderList(null, { status: "no_resume" });
    expect(screen.getByText("Upload a resume to prioritize jobs")).toBeInTheDocument();
  });

  it("paginates", () => {
    const { onPageChange } = renderList(
      response([item("a")], {
        pagination: { page: 1, page_size: 1, total: 2, total_pages: 2 },
      }),
    );

    fireEvent.click(screen.getByRole("button", { name: "Next →" }));

    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it("keeps long content inside a narrow viewport", () => {
    renderList(
      response([
        item("a", {}, {
          title: "Principal Distributed Systems Reliability Engineering Lead (Payments Infrastructure)",
          location: "San Francisco Bay Area, California, United States of America",
        }),
      ]),
    );

    const article = screen.getAllByRole("article")[0];
    // Titles and reasons wrap; the text column can shrink; score tiles
    // share the row instead of forcing a fixed width.
    expect(within(article).getByRole("heading", { level: 4 }).className).toContain("break-words");
    expect(article.querySelector(".min-w-0.flex-1")).not.toBeNull();
    expect(article.querySelector(".grid.grid-cols-2")).not.toBeNull();
    expect(article.innerHTML).not.toMatch(/\bw-\[\d+px\]/);
  });
});
