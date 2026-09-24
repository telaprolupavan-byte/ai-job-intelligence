// AJI-023 (Job Search) — the search-criteria contract the Jobs page sends
// to GET /jobs, kept in step with the API's own validation
// (apps/api/services/job_listing.py). Pure helpers, no requests.

import { ApiError } from "./api";

/** Mirrors the API's SEARCH_TEXT_MAX_LENGTH; a longer value is a 422. */
export const JOB_SEARCH_TEXT_MAX_LENGTH = 200;

/** The filter values GET /jobs accepts; anything else is a 422. */
export const EMPLOYMENT_TYPE_FILTERS = [
  "full_time",
  "contract",
  "part_time",
  "internship",
  "temporary",
] as const;

export const REMOTE_TYPE_FILTERS = ["remote", "hybrid", "onsite"] as const;

/** `value` if it is one of `allowed`, else "" (no filter). */
export function allowedOrEmpty(
  value: string | null,
  allowed: readonly string[],
): string {
  return value && allowed.includes(value) ? value : "";
}

/** Blank means "no criterion"; inner runs of whitespace collapse, the
 *  same cleaning the API applies. */
export function cleanCriterion(value: string): string {
  return value.split(/\s+/).filter(Boolean).join(" ");
}

export type SearchError = {
  message: string;
  /** A 422 means the criteria themselves were rejected; repeating the
   *  same request cannot succeed, so only other failures offer a retry. */
  retryable: boolean;
};

export function toSearchError(err: unknown): SearchError {
  if (err instanceof ApiError && err.status === 422) {
    return {
      message:
        "Some search criteria weren't accepted. Check them and search again.",
      retryable: false,
    };
  }

  return {
    message: "Unable to load jobs. Please try again.",
    retryable: true,
  };
}
