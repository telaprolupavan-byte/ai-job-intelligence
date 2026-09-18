"use client";

import { useState } from "react";
import Panel from "@/components/app/panel";
import Badge from "@/components/app/badge";
import { cn } from "@/lib/utils";
import type { DashboardData } from "@/lib/dashboard";

type Props = {
  jobs: DashboardData["jobs"];
  resumeReady: boolean;
};

type EmploymentFilter = "full_time" | "contract";

const FILTER_LABEL: Record<EmploymentFilter, string> = {
  full_time: "Full-Time",
  contract: "Contract",
};

function formatEmploymentType(employmentType: string | null): string {
  if (!employmentType) return "Unspecified";

  return employmentType
    .split("_")
    .map((word) => word[0]?.toUpperCase() + word.slice(1))
    .join(" ");
}

export default function TodayJobs({ jobs, resumeReady }: Props) {
  const [filter, setFilter] = useState<EmploymentFilter>("full_time");

  const filteredJobs = jobs.recent.filter(
    (job) => job.employment_type === filter,
  );

  return (
    <Panel padding="lg">
      <h2 className="text-xl font-bold text-app-text">Today&apos;s jobs</h2>

      <p className="mt-2 text-[13px] text-app-muted">
        {resumeReady
          ? "Fresh listings discovered today, matched to your resume."
          : "Job discovery starts after your resume is ready."}
      </p>

      <div className="mt-6 flex gap-2">
        {(Object.keys(FILTER_LABEL) as EmploymentFilter[]).map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => setFilter(option)}
            className={cn(
              "app-focus-ring rounded-full px-4 py-1.5 text-xs font-medium uppercase tracking-wider transition",
              filter === option
                ? "bg-app-blue-soft text-app-blue"
                : "border border-app-border bg-app-surface text-app-body hover:border-app-border-strong",
            )}
          >
            {FILTER_LABEL[option]}
          </button>
        ))}
      </div>

      <div className="mt-6 border-t border-app-border pt-6">
        {!resumeReady ? (
          <div>
            <h3 className="text-sm font-bold text-app-body">
              No jobs to display yet
            </h3>
            <p className="mt-2 text-xs text-app-faint">
              Complete resume analysis to unlock job intelligence.
            </p>
          </div>
        ) : filteredJobs.length === 0 ? (
          <div>
            <h3 className="text-sm font-bold text-app-body">
              {jobs.recent.length === 0
                ? "No jobs to display yet"
                : `No ${FILTER_LABEL[filter].toLowerCase()} jobs right now`}
            </h3>
            <p className="mt-2 text-xs text-app-faint">
              {jobs.recent.length === 0
                ? "New listings will appear here as they're discovered."
                : "Try the other filter, or browse the full jobs list."}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-app-border">
            {filteredJobs.map((job) => (
              <div
                key={job.id}
                className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-app-text">
                    {job.title}
                  </div>
                  <div className="mt-1 truncate text-xs text-app-muted">
                    {job.company ?? "Unknown company"}
                    {job.location ? ` · ${job.location}` : ""}
                  </div>
                </div>

                <Badge tone="blue-soft" className="shrink-0">
                  {formatEmploymentType(job.employment_type)}
                </Badge>
              </div>
            ))}
          </div>
        )}
      </div>
    </Panel>
  );
}
