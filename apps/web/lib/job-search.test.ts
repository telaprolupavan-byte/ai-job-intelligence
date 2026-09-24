// AJI-023 (Job Search) — the pure search-criteria helpers and the
// formatters the listing card and the job detail view share.
import { describe, expect, it } from "vitest";

import { ApiError } from "./api";
import type { Job } from "./jobs";
import { formatPostedDate, formatSalary } from "./job-format";
import {
  EMPLOYMENT_TYPE_FILTERS,
  REMOTE_TYPE_FILTERS,
  allowedOrEmpty,
  cleanCriterion,
  toSearchError,
} from "./job-search";

function job(overrides: Partial<Job>): Job {
  return {
    id: "j",
    title: "Engineer",
    company: null,
    location: null,
    country: "USA",
    remote_type: null,
    employment_type: null,
    salary_min: null,
    salary_max: null,
    salary_currency: null,
    contract_duration: null,
    contract_worker_type: null,
    description: null,
    requirements: null,
    responsibilities: null,
    posting_date: null,
    source: "greenhouse",
    source_url: null,
    application_url: null,
    first_seen_at: "2026-09-01T00:00:00",
    last_seen_at: "2026-09-01T00:00:00",
    ...overrides,
  };
}

describe("search criteria", () => {
  it("mirrors the API's filter vocabularies", () => {
    // Pinned against apps/api/services/job_listing.py (itself pinned to
    // the discovery normalizer by tests/test_job_search_api.py).
    expect([...EMPLOYMENT_TYPE_FILTERS].sort()).toEqual([
      "contract",
      "full_time",
      "internship",
      "part_time",
      "temporary",
    ]);
    expect([...REMOTE_TYPE_FILTERS].sort()).toEqual([
      "hybrid",
      "onsite",
      "remote",
    ]);
  });

  it("drops filter values the API would reject", () => {
    expect(allowedOrEmpty("contract", EMPLOYMENT_TYPE_FILTERS)).toBe(
      "contract",
    );
    expect(allowedOrEmpty("Full-Time", EMPLOYMENT_TYPE_FILTERS)).toBe("");
    expect(allowedOrEmpty(null, REMOTE_TYPE_FILTERS)).toBe("");
  });

  it("trims and collapses free text; blank means no criterion", () => {
    expect(cleanCriterion("  senior   engineer ")).toBe("senior engineer");
    expect(cleanCriterion(" \t ")).toBe("");
  });

  it("treats a 422 as invalid criteria with no retry", () => {
    expect(toSearchError(new ApiError("bad", 422))).toEqual({
      message:
        "Some search criteria weren't accepted. Check them and search again.",
      retryable: false,
    });
  });

  it("treats every other failure as retryable", () => {
    for (const err of [
      new ApiError("down", 503),
      new ApiError("timeout", 0),
      new TypeError("Failed to fetch"),
    ]) {
      expect(toSearchError(err)).toEqual({
        message: "Unable to load jobs. Please try again.",
        retryable: true,
      });
    }
  });
});

describe("formatSalary", () => {
  it("never invents a currency the source did not state", () => {
    expect(formatSalary(job({ salary_min: 90000, salary_max: 120000 }))).toBe(
      "90,000 – 120,000",
    );
    expect(formatSalary(job({ salary_min: 90000 }))).toBe("From 90,000");
    expect(formatSalary(job({ salary_max: 120000 }))).toBe("Up to 120,000");
  });

  it("uses the stated currency", () => {
    expect(
      formatSalary(
        job({ salary_min: 90000, salary_max: 120000, salary_currency: "USD" }),
      ),
    ).toBe("USD 90,000 – 120,000");
    expect(
      formatSalary(
        job({ salary_min: 50, salary_max: 50, salary_currency: "USD" }),
      ),
    ).toBe("USD 50");
  });

  it("is null when no amount is known", () => {
    expect(formatSalary(job({ salary_currency: "USD" }))).toBeNull();
  });
});

describe("formatPostedDate", () => {
  it("shows the stored UTC calendar date without shifting it", () => {
    expect(formatPostedDate("2026-09-01T00:00:00")).toBe("Sep 1, 2026");
    expect(formatPostedDate("2026-09-01T23:59:59")).toBe("Sep 1, 2026");
    expect(formatPostedDate("2026-09-01T09:00:00+00:00")).toBe("Sep 1, 2026");
    expect(formatPostedDate("2026-09-01")).toBe("Sep 1, 2026");
  });

  it("is null when there is no usable date", () => {
    expect(formatPostedDate(null)).toBeNull();
    expect(formatPostedDate("not a date")).toBeNull();
  });
});
