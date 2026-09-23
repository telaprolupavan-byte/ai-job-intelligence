// AJI-025 — Job Priority Ranking (GET /jobs/priority).
//
// The ordering is computed server-side by a deterministic engine
// (services/priority_ranking): Hard Eligibility is a gate, then Job Match,
// then ATS Alignment for one resume version, then the listing's own order.
// There is no priority score: Job Match and ATS Alignment are never
// combined into one number, and each stays visible on its own. This file
// only fetches that result and names its states for display.

import { apiRequest } from "./api";
import { getAuthToken } from "./auth";
import type { EligibilityStatus, Job } from "./jobs";

export type PriorityState = "ranked" | "partial" | "not_ready" | "excluded";

export type PriorityReasonSource = "eligibility" | "job_match" | "ats_alignment";

export type PriorityReason = {
  code: string;
  source: PriorityReasonSource;
  /** "evidence": a fact the ordering used. "caution": a limitation of it. */
  kind: "evidence" | "caution";
  message: string;
};

export type PriorityBlockingFactor = {
  code: string;
  source: PriorityReasonSource;
  message: string;
};

export type PriorityInputs = {
  eligibility: {
    status: EligibilityStatus;
    engine_version: string;
    failed_constraints: string[];
    unknown_constraints: string[];
  };
  job_match: {
    id: string;
    score: number;
    confidence: string;
    engine_version: string;
    job_intelligence_id: string | null;
    /** false = recalculating would produce a newer result. */
    current: boolean;
    created_at: string;
  } | null;
  ats_alignment: {
    id: string;
    overall_score: number;
    confidence: string;
    must_have_matched: number | null;
    must_have_total: number | null;
    engine_version: string;
    requirement_intelligence_id: string | null;
    current: boolean;
    created_at: string;
  } | null;
};

export type JobPriorityItem = {
  job: Job;
  /** 1-based position among ranked/partial jobs; null when not ranked. */
  rank: number | null;
  state: PriorityState;
  eligibility_status: EligibilityStatus;
  reasons: PriorityReason[];
  blocking_factors: PriorityBlockingFactor[];
  inputs: PriorityInputs;
};

export type JobPriorityResponse = {
  engine_version: string;
  ordering: string[];
  generated_at: string;
  user_id: string;
  resume_version: {
    id: string;
    name: string;
    resume_filename: string;
    is_master: boolean;
  } | null;
  counts: Record<PriorityState, number> & { unanalyzed: number };
  items: JobPriorityItem[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
};

export type JobPriorityParams = {
  resumeVersionId?: string;
  search?: string;
  employment_type?: string;
  remote_type?: string;
  location?: string;
  page?: number;
  page_size?: number;
};

export function buildJobPriorityQuery(params: JobPriorityParams): string {
  const searchParams = new URLSearchParams();

  if (params.resumeVersionId) {
    searchParams.set("resume_version_id", params.resumeVersionId);
  }
  if (params.search) searchParams.set("search", params.search);
  if (params.employment_type) {
    searchParams.set("employment_type", params.employment_type);
  }
  if (params.remote_type) searchParams.set("remote_type", params.remote_type);
  if (params.location) searchParams.set("location", params.location);

  searchParams.set("page", String(params.page ?? 1));
  searchParams.set("page_size", String(params.page_size ?? 20));

  return searchParams.toString();
}

export async function getJobPriority(
  params: JobPriorityParams,
): Promise<JobPriorityResponse> {
  const token = getAuthToken();

  return apiRequest<JobPriorityResponse>(
    `/jobs/priority?${buildJobPriorityQuery(params)}`,
    {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      cache: "no-store",
    },
    20_000,
  );
}

export const PRIORITY_STATE_DISPLAY: Record<
  PriorityState,
  {
    label: string;
    tone: "success-soft" | "blue-soft" | "neutral-soft" | "danger";
  }
> = {
  ranked: { label: "Ranked", tone: "success-soft" },
  partial: { label: "Ranked · partial evidence", tone: "blue-soft" },
  not_ready: { label: "Not ranked yet", tone: "neutral-soft" },
  excluded: { label: "Excluded", tone: "danger" },
};

export type PrioritySections = {
  /** ranked + partial, already in priority order. */
  ordered: JobPriorityItem[];
  notReady: JobPriorityItem[];
  excluded: JobPriorityItem[];
};

/** Splits one page of items by state, keeping the server's order. */
export function splitPriorityItems(items: JobPriorityItem[]): PrioritySections {
  return {
    ordered: items.filter(
      (item) => item.state === "ranked" || item.state === "partial",
    ),
    notReady: items.filter((item) => item.state === "not_ready"),
    excluded: items.filter((item) => item.state === "excluded"),
  };
}

/** Whole-percent display, rounded like the rest of the Jobs page. */
export function formatPercent(score: number): string {
  return `${Math.round(score)}%`;
}
