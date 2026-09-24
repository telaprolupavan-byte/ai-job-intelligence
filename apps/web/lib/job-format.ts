// Shared job label formatting for the Jobs page and its Priority view
// (AJI-025), moved unchanged out of app/(app)/jobs/page.tsx so both render
// employment type and origin identically.

import type { Job } from "./jobs";

export function formatValue(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

// AJI-024: Full-Time and Contract must stay distinguishable at a glance,
// so each gets its own chip treatment; contract length rides on the chip.
export function employmentTypeTone(
  employmentType: string,
): "blue-soft" | "neutral-soft" | "neutral" {
  if (employmentType === "full_time") return "blue-soft";
  if (employmentType === "contract") return "neutral-soft";
  return "neutral";
}

export function formatEmploymentType(job: Job): string {
  if (job.employment_type === "full_time") return "Full-Time";

  if (job.employment_type === "contract") {
    return job.contract_duration
      ? `Contract · ${job.contract_duration}`
      : "Contract";
  }

  return formatValue(job.employment_type ?? "");
}

// AJI-024: discovered (shared) vs. the user's own private submission
// (AJI-022), without leaking internal source identifiers for the latter.
export function formatJobOrigin(job: Job): string {
  if (job.origin === "user_submitted" || job.source === "user_submitted") {
    return "Added by you · private";
  }

  // AJI-030: covers every synthetic source (fixture, development dataset).
  if (job.is_test_data) return "Synthetic · development data";

  // AJI-028: the source's registered display name when it has one.
  return `Discovered · ${job.source_attribution?.name ?? formatValue(job.source)}`;
}

// AJI-028: the visible credit a source's terms require ("Job via X",
// linking to the posting on X). Null when the source does not require
// one, or there is nowhere safe to link - the API only ever returns an
// absolute http(s) URL here.
export function sourceAttributionLink(
  job: Job,
): { label: string; href: string } | null {
  const attribution = job.source_attribution;

  if (!attribution?.requires_link_back || !attribution.url) return null;

  if (!/^https?:\/\//i.test(attribution.url)) return null;

  return { label: `Job via ${attribution.name}`, href: attribution.url };
}

// AJI-023 (Job Search): moved here from app/(app)/jobs/page.tsx so the
// listing card and the job detail view format pay identically. A missing
// currency stays missing - it used to be shown as "USD", which invented a
// fact the source never stated. Returns null when no amount is known.
export function formatSalary(job: Job): string | null {
  const currency = job.salary_currency?.trim() || null;
  const amount = (value: number) => value.toLocaleString("en-US");
  const withCurrency = (text: string) =>
    currency ? `${currency} ${text}` : text;

  if (job.salary_min !== null && job.salary_max !== null) {
    return withCurrency(
      job.salary_min === job.salary_max
        ? amount(job.salary_min)
        : `${amount(job.salary_min)} – ${amount(job.salary_max)}`,
    );
  }

  if (job.salary_min !== null) {
    return `From ${withCurrency(amount(job.salary_min))}`;
  }

  if (job.salary_max !== null) {
    return `Up to ${withCurrency(amount(job.salary_max))}`;
  }

  return null;
}

// `posting_date` (and, AJI-028, `expires_at`) is stored as naive UTC (see
// services/job_discovery/persistence.py::to_naive_utc), so it is read and
// shown as a UTC calendar date - never shifted into the viewer's timezone,
// which could move it to the previous or next day. Null when the source
// gave no date or the value is unreadable.
export function formatPostedDate(value: string | null): string | null {
  if (!value) return null;

  const iso = /^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value;
  const hasOffset = /(Z|[+-]\d{2}:?\d{2})$/.test(iso);
  const date = new Date(hasOffset ? iso : `${iso}Z`);

  if (Number.isNaN(date.getTime())) return null;

  return date.toLocaleDateString("en-US", {
    timeZone: "UTC",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
