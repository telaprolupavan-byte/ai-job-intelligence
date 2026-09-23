"use client";

import { ListOrdered } from "lucide-react";
import type { Job } from "@/lib/jobs";
import {
  employmentTypeTone,
  formatEmploymentType,
  formatJobOrigin,
  formatValue,
} from "@/lib/job-format";
import {
  PRIORITY_STATE_DISPLAY,
  formatPercent,
  splitPriorityItems,
  type JobPriorityItem,
  type JobPriorityResponse,
} from "@/lib/job-priority";
import AppButton from "./app-button";
import Badge from "./badge";
import EmptyState from "./empty-state";
import ErrorState from "./error-state";
import Panel from "./panel";
import { Skeleton } from "./skeleton";

// AJI-025 — the Jobs page's Priority view. Renders GET /jobs/priority as
// the server ordered it: jobs the user has analyzed, gated by Hard
// Eligibility, then ordered by Job Match, then ATS Alignment for one
// resume version. It shows NO priority score - Job Match and ATS
// Alignment keep their own, separately labelled values - and makes no
// recommendation: the order is a starting point, the decision is the
// user's, and NERO never applies on their behalf.

export type JobPriorityListStatus = "loading" | "error" | "no_resume" | "ready";

type JobPriorityListProps = {
  status: JobPriorityListStatus;
  result: JobPriorityResponse | null;
  error?: string | null;
  onRetry: () => void;
  onOpenJob: (jobId: string) => void;
  onPageChange: (page: number) => void;
  /** This user's tracking status per job id — context only, never order. */
  applicationStatusByJobId?: Record<string, string>;
};

const ELIGIBILITY_DISPLAY = {
  eligible: { label: "Eligible", tone: "blue" },
  unknown: { label: "Eligibility unknown", tone: "neutral" },
  ineligible: { label: "Ineligible", tone: "danger" },
} as const;

export default function JobPriorityList({
  status,
  result,
  error,
  onRetry,
  onOpenJob,
  onPageChange,
  applicationStatusByJobId = {},
}: JobPriorityListProps) {
  if (status === "loading") {
    return (
      <div className="space-y-4" aria-busy="true">
        <p role="status" className="text-xs text-app-faint">
          Ordering your analyzed jobs…
        </p>
        {Array.from({ length: 2 }).map((_, index) => (
          <div
            key={index}
            className="rounded-xl border border-app-border bg-app-panel p-6"
          >
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="mt-3 h-5 w-2/3" />
            <Skeleton className="mt-5 h-12 w-full" />
          </div>
        ))}
      </div>
    );
  }

  if (status === "error") {
    return (
      <ErrorState
        title="Priority unavailable"
        message={error || "Unable to load job priority. Please try again."}
        onRetry={onRetry}
      />
    );
  }

  if (status === "no_resume") {
    return (
      <EmptyState
        icon={ListOrdered}
        title="Upload a resume to prioritize jobs"
        description="Priority orders jobs by their Job Match and ATS Alignment, and both are calculated against a resume."
        action={
          <AppButton href="/resume" variant="secondary">
            Go to Resume
          </AppButton>
        }
      />
    );
  }

  if (!result) return null;

  const { ordered, notReady, excluded } = splitPriorityItems(result.items);
  const counts = result.counts;
  const rankedTotal = counts.ranked + counts.partial;
  // Every job in this view (same filters as All jobs), analyzed or not,
  // so a position is never read as a place among every known job.
  const jobsInView =
    rankedTotal + counts.not_ready + counts.excluded + counts.unanalyzed;
  const resumeName = result.resume_version
    ? `${result.resume_version.name} (${result.resume_version.resume_filename})`
    : null;

  return (
    <div className="space-y-5">
      <Panel as="section" padding="md">
        <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-app-blue">
          How priority works
        </div>
        <p
          id="priority-explainer"
          className="mt-2 max-w-3xl text-xs leading-5 text-app-muted"
        >
          Priority ranks only the jobs that already have a Job Match for
          this resume version, so &ldquo;Priority 1 of {rankedTotal}&rdquo;
          means first among those {rankedTotal} ranked jobs, not among
          every job NERO has found. Jobs your hard requirements rule out
          are excluded. The rest are ordered by Job Match, with jobs
          confirmed eligible ahead of jobs whose eligibility is unknown,
          and ATS Alignment decides only between equal Job Match scores.
          The two scores are shown separately and are never combined.
          Your tracking status (saved, applied, rejected and so on)
          doesn&apos;t change the order. Priority is a starting point for
          your attention. It doesn&apos;t predict interviews or offers, and
          NERO never applies for you.
        </p>
        {resumeName && (
          <p className="mt-2 break-words text-[11px] leading-5 text-app-faint">
            Based on <span className="text-app-body">{resumeName}</span>.
          </p>
        )}
        <p
          className="mt-3 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[10px] uppercase tracking-[0.12em] text-app-faint"
          aria-label="Priority summary"
        >
          <span>{jobsInView} jobs in view</span>
          <span>{rankedTotal} ranked</span>
          <span>{counts.not_ready} not ranked yet</span>
          <span>{counts.excluded} excluded</span>
          <span>{counts.unanalyzed} not analyzed</span>
        </p>
      </Panel>

      {result.items.length === 0 && (
        <EmptyState
          icon={ListOrdered}
          title="No analyzed jobs to prioritize yet"
          description="Open a job and calculate its Job Match for this resume version to include it here."
        />
      )}

      {ordered.length > 0 && (
        <section aria-labelledby="priority-ranked-heading">
          <h3
            id="priority-ranked-heading"
            className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-app-blue"
          >
            Ranked jobs
          </h3>
          <ol className="space-y-4" aria-label="Ranked jobs">
            {ordered.map((item) => (
              <li key={item.job.id}>
                <PriorityJobCard
                  item={item}
                  rankedTotal={rankedTotal}
                  onOpenJob={onOpenJob}
                  applicationStatus={applicationStatusByJobId[item.job.id]}
                />
              </li>
            ))}
          </ol>
        </section>
      )}

      {notReady.length > 0 && (
        <section aria-labelledby="priority-not-ready-heading">
          <h3
            id="priority-not-ready-heading"
            className="font-mono text-[10px] uppercase tracking-[0.18em] text-app-blue"
          >
            Not ranked yet
          </h3>
          <p className="mb-3 mt-1 text-xs leading-5 text-app-faint">
            These have no Job Match for this resume version, so there is
            nothing to order them by yet. That is not a low priority.
          </p>
          <ul className="space-y-4">
            {notReady.map((item) => (
              <li key={item.job.id}>
                <PriorityJobCard
                  item={item}
                  rankedTotal={rankedTotal}
                  onOpenJob={onOpenJob}
                  applicationStatus={applicationStatusByJobId[item.job.id]}
                />
              </li>
            ))}
          </ul>
        </section>
      )}

      {excluded.length > 0 && (
        <section aria-labelledby="priority-excluded-heading">
          <h3
            id="priority-excluded-heading"
            className="font-mono text-[10px] uppercase tracking-[0.18em] text-app-blue"
          >
            Excluded by your hard requirements
          </h3>
          <p className="mb-3 mt-1 text-xs leading-5 text-app-faint">
            Hard Eligibility rules these out, whatever their Job Match or
            ATS Alignment. Change your hard requirements in Settings if one
            no longer applies.
          </p>
          <ul className="space-y-4">
            {excluded.map((item) => (
              <li key={item.job.id}>
                <PriorityJobCard
                  item={item}
                  rankedTotal={rankedTotal}
                  onOpenJob={onOpenJob}
                  applicationStatus={applicationStatusByJobId[item.job.id]}
                />
              </li>
            ))}
          </ul>
        </section>
      )}

      {counts.unanalyzed > 0 && result.items.length > 0 && (
        <p className="text-xs leading-5 text-app-faint">
          {counts.unanalyzed === 1
            ? "1 other job has"
            : `${counts.unanalyzed} other jobs have`}{" "}
          no Job Match or ATS Alignment for this resume version, so{" "}
          {counts.unanalyzed === 1 ? "it isn't" : "they aren't"} included.
        </p>
      )}

      {result.pagination.total_pages > 1 && (
        <div className="flex items-center justify-center gap-5">
          <AppButton
            variant="ghost"
            size="sm"
            disabled={result.pagination.page <= 1}
            onClick={() => onPageChange(result.pagination.page - 1)}
          >
            ← Previous
          </AppButton>
          <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-app-faint">
            Page {result.pagination.page} / {result.pagination.total_pages}
          </div>
          <AppButton
            variant="ghost"
            size="sm"
            disabled={result.pagination.page >= result.pagination.total_pages}
            onClick={() => onPageChange(result.pagination.page + 1)}
          >
            Next →
          </AppButton>
        </div>
      )}
    </div>
  );
}

function PriorityJobCard({
  item,
  rankedTotal,
  onOpenJob,
  applicationStatus,
}: {
  item: JobPriorityItem;
  rankedTotal: number;
  onOpenJob: (jobId: string) => void;
  applicationStatus?: string;
}) {
  const { job, inputs } = item;
  const state = PRIORITY_STATE_DISPLAY[item.state];
  const eligibility = ELIGIBILITY_DISPLAY[item.eligibility_status];
  const titleId = `priority-job-${job.id}`;
  const evidence = item.reasons.filter((reason) => reason.kind === "evidence");
  const cautions = item.reasons.filter((reason) => reason.kind === "caution");

  return (
    <article
      aria-labelledby={titleId}
      className="overflow-hidden rounded-xl border border-app-border bg-app-panel p-5"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {item.rank !== null && (
              <span
                className="font-mono text-[10px] uppercase tracking-[0.15em] text-app-blue"
                data-testid="priority-position"
              >
                Priority {item.rank} of {rankedTotal} ranked
              </span>
            )}
            <Badge tone={state.tone}>{state.label}</Badge>
            <Badge tone={eligibility.tone}>{eligibility.label}</Badge>
            {applicationStatus && (
              <Badge tone="neutral-soft">
                Tracking: {formatValue(applicationStatus)}
              </Badge>
            )}
          </div>

          <h4
            id={titleId}
            className="mt-3 break-words text-lg font-semibold tracking-tight text-app-text"
          >
            {job.title}
          </h4>
          <p className="mt-1 break-words text-sm text-app-muted">
            {job.company || "Company not specified"}
          </p>

          <JobMeta job={job} />
        </div>

        <AppButton
          variant="primary"
          size="sm"
          onClick={() => onOpenJob(job.id)}
          aria-label={`Open job workflow for ${job.title}`}
          className="self-start"
        >
          Open job
        </AppButton>
      </div>

      {item.state !== "excluded" && (
        <div className="mt-4 grid grid-cols-2 gap-3">
          <ScoreTile
            label="Job Match"
            value={inputs.job_match ? formatPercent(inputs.job_match.score) : null}
            outOfDate={inputs.job_match ? !inputs.job_match.current : false}
          />
          <ScoreTile
            label="ATS Alignment"
            value={
              inputs.ats_alignment
                ? formatPercent(inputs.ats_alignment.overall_score)
                : null
            }
            outOfDate={
              inputs.ats_alignment ? !inputs.ats_alignment.current : false
            }
          />
        </div>
      )}

      {item.blocking_factors.length > 0 && (
        <ReasonList
          title={item.state === "excluded" ? "Ruled out by" : "Why it isn't ranked"}
          items={item.blocking_factors.map((factor) => factor.message)}
          tone="blocking"
        />
      )}

      {cautions.length > 0 && (
        <ReasonList
          title="Keep in mind"
          items={cautions.map((reason) => reason.message)}
          tone="caution"
        />
      )}

      {evidence.length > 0 && (
        <ReasonList
          title="Based on"
          items={evidence.map((reason) => reason.message)}
          tone="evidence"
        />
      )}
    </article>
  );
}

function JobMeta({ job }: { job: Job }) {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      {job.is_test_data && <Badge tone="danger">Test data</Badge>}
      {job.employment_type && (
        <Badge tone={employmentTypeTone(job.employment_type)}>
          {formatEmploymentType(job)}
        </Badge>
      )}
      {job.location && (
        <Badge className="max-w-full break-all">{job.location}</Badge>
      )}
      {job.remote_type && <Badge>{formatValue(job.remote_type)}</Badge>}
      <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-blue">
        {formatJobOrigin(job)}
      </span>
    </div>
  );
}

function ScoreTile({
  label,
  value,
  outOfDate,
}: {
  label: string;
  value: string | null;
  outOfDate: boolean;
}) {
  return (
    <div
      className="min-w-0 rounded-lg border border-app-border bg-app-bg p-3"
      aria-label={`${label}: ${value ?? "not calculated"}`}
    >
      <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
        {label}
      </div>
      <div className="mt-1 text-xl font-bold text-app-text">
        {value ?? "—"}
      </div>
      <div className="mt-0.5 text-[11px] leading-4 text-app-faint">
        {value === null ? "Not calculated" : outOfDate ? "Out of date" : "Current"}
      </div>
    </div>
  );
}

const REASON_TONE = {
  evidence: "text-app-muted",
  caution: "text-app-body",
  blocking: "text-app-danger-text",
} as const;

function ReasonList({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: keyof typeof REASON_TONE;
}) {
  return (
    <div className="mt-4">
      <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
        {title}
      </div>
      <ul className={`mt-1.5 space-y-1 text-xs leading-5 ${REASON_TONE[tone]}`}>
        {items.map((message, index) => (
          <li key={`${index}-${message}`} className="break-words">
            {message}
          </li>
        ))}
      </ul>
    </div>
  );
}
