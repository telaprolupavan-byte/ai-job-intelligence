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

  if (job.is_test_data) return "Discovered · test fixture";

  return `Discovered · ${formatValue(job.source)}`;
}
