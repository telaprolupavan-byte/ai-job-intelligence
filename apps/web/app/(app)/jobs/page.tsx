"use client";

import { useEffect, useState, useTransition } from "react";
import {
  calculateJobMatch,
  getJobs,
  type Job,
  type JobMatchResult,
} from "../../../lib/jobs";

type JobFilters = {
  search: string;
  employmentType: string;
  remoteType: string;
  location: string;
};

const EMPTY_FILTERS: JobFilters = {
  search: "",
  employmentType: "",
  remoteType: "",
  location: "",
};

type JobResults = {
  jobs: Job[];
  totalPages: number;
  totalJobs: number;
};

const EMPTY_RESULTS: JobResults = {
  jobs: [],
  totalPages: 0,
  totalJobs: 0,
};

export default function Page() {
  // Draft state bound to the filter form inputs, not yet submitted.
  const [filterForm, setFilterForm] = useState<JobFilters>(EMPTY_FILTERS);

  // The filters actually applied to the last/current search request.
  const [appliedFilters, setAppliedFilters] =
    useState<JobFilters>(EMPTY_FILTERS);

  const [page, setPage] = useState(1);
  const [results, setResults] = useState<JobResults>(EMPTY_RESULTS);
  const [error, setError] = useState<string | null>(null);
  const [matches, setMatches] = useState<Record<string, JobMatchResult>>({});

  // Keyed by job id so concurrent match requests for different jobs never
  // overwrite each other's loading/error state.
  const [matchingJobIds, setMatchingJobIds] = useState<
    Record<string, boolean>
  >({});
  const [matchErrors, setMatchErrors] = useState<Record<string, string>>({});
  const [isPending, startTransition] = useTransition();
  useEffect(() => {
    let cancelled = false;
    startTransition(async () => {
      try {
        const response = await getJobs({
          search: appliedFilters.search || undefined,
          employment_type: appliedFilters.employmentType || undefined,
          remote_type: appliedFilters.remoteType || undefined,
          location: appliedFilters.location || undefined,
          page,
          page_size: 20,
        });

        if (cancelled) {
          return;
        }

        setResults({
          jobs: response.jobs,
          totalPages: response.pagination.total_pages,
          totalJobs: response.pagination.total,
        });
        setError(null);
      } catch (err) {
        if (cancelled) {
          return;
        }

        console.error(err);
        setError("Unable to load jobs. Please try again.");
      }
    });

    return () => {
      cancelled = true;
    };
  }, [appliedFilters, page]);

  function handleSearch(event: React.FormEvent) {
    event.preventDefault();
    setAppliedFilters(filterForm);
    setPage(1);
  }

  function clearFilters() {
    setFilterForm(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
    setPage(1);
  }
  async function handleCalculateMatch(jobId: string) {
    setMatchingJobIds((current) => ({ ...current, [jobId]: true }));
    setMatchErrors((current) => {
      const next = { ...current };
      delete next[jobId];
      return next;
    });

    try {
      const match = await calculateJobMatch(jobId);

      setMatches((current) => ({
        ...current,
        [jobId]: match,
      }));
    } catch (err) {
      console.error(err);

      setMatchErrors((current) => ({
        ...current,
        [jobId]:
          err instanceof Error
            ? err.message
            : "Unable to calculate job match.",
      }));
    } finally {
      setMatchingJobIds((current) => {
        const next = { ...current };
        delete next[jobId];
        return next;
      });
    }
  }

  return (
    <main className="min-h-screen bg-[#05070A] px-6 py-8 text-[#F2F5F8]">
      <div className="mx-auto max-w-7xl">

        {/* HEADER */}
        <div className="mb-8">
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-[#E50920]">
            Intelligence Module
          </div>

          <div className="mt-3 flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">
                Job Discovery
              </h1>

              <p className="mt-2 max-w-2xl text-sm leading-7 text-[#8D9AAA]">
                Discover U.S. opportunities from connected job sources.
                Search, filter, and inspect available positions.
              </p>
            </div>

            <div className="border border-[#1A3048] bg-[#0B1626] px-4 py-3">
              <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-[#1677E8]">
                ACTIVE LISTINGS
              </div>

              <div className="mt-1 text-xl font-bold">
                {isPending ? "—" : results.totalJobs}
              </div>
            </div>
          </div>
        </div>

        {/* FILTER PANEL */}
        <form
          onSubmit={handleSearch}
          className="mb-8 border border-[#1A3048] bg-[#0B1626] p-5"
        >
          <div className="mb-5 flex items-center justify-between border-b border-[#1A3048] pb-4">
            <div>
              <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-[#1677E8]">
                SEARCH PARAMETERS
              </div>

              <div className="mt-1 text-sm text-[#8D9AAA]">
                Configure discovery criteria
              </div>
            </div>

            <div className="hidden font-mono text-[9px] uppercase tracking-[0.15em] text-[#506174] md:block">
              AJI / DISCOVERY
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">

            {/* SEARCH */}
            <div>
              <label
                htmlFor="search"
                className="mb-2 block font-mono text-[9px] uppercase tracking-[0.15em] text-[#8D9AAA]"
              >
                Role / Keyword
              </label>

              <input
                id="search"
                type="text"
                value={filterForm.search}
                onChange={(event) =>
                  setFilterForm((current) => ({
                    ...current,
                    search: event.target.value,
                  }))
                }
                placeholder="AI Engineer"
                className="w-full border border-[#1A3048] bg-[#05070A] px-3 py-3 text-sm text-[#F2F5F8] outline-none placeholder:text-[#506174] focus:border-[#1677E8]"
              />
            </div>

            {/* EMPLOYMENT TYPE */}
            <div>
              <label
                htmlFor="employmentType"
                className="mb-2 block font-mono text-[9px] uppercase tracking-[0.15em] text-[#8D9AAA]"
              >
                Employment Type
              </label>

              <select
                id="employmentType"
                value={filterForm.employmentType}
                onChange={(event) =>
                  setFilterForm((current) => ({
                    ...current,
                    employmentType: event.target.value,
                  }))
                }
                className="w-full border border-[#1A3048] bg-[#05070A] px-3 py-3 text-sm text-[#F2F5F8] outline-none focus:border-[#1677E8]"
              >
                <option value="">All Types</option>
                <option value="full_time">Full Time</option>
                <option value="contract">Contract</option>
                <option value="part_time">Part Time</option>
                <option value="internship">Internship</option>
                <option value="temporary">Temporary</option>
              </select>
            </div>

            {/* REMOTE TYPE */}
            <div>
              <label
                htmlFor="remoteType"
                className="mb-2 block font-mono text-[9px] uppercase tracking-[0.15em] text-[#8D9AAA]"
              >
                Work Arrangement
              </label>

              <select
                id="remoteType"
                value={filterForm.remoteType}
                onChange={(event) =>
                  setFilterForm((current) => ({
                    ...current,
                    remoteType: event.target.value,
                  }))
                }
                className="w-full border border-[#1A3048] bg-[#05070A] px-3 py-3 text-sm text-[#F2F5F8] outline-none focus:border-[#1677E8]"
              >
                <option value="">All Arrangements</option>
                <option value="remote">Remote</option>
                <option value="hybrid">Hybrid</option>
                <option value="onsite">On-site</option>
              </select>
            </div>

            {/* LOCATION */}
            <div>
              <label
                htmlFor="location"
                className="mb-2 block font-mono text-[9px] uppercase tracking-[0.15em] text-[#8D9AAA]"
              >
                Location
              </label>

              <input
                id="location"
                type="text"
                value={filterForm.location}
                onChange={(event) =>
                  setFilterForm((current) => ({
                    ...current,
                    location: event.target.value,
                  }))
                }
                placeholder="New York, NY"
                className="w-full border border-[#1A3048] bg-[#05070A] px-3 py-3 text-sm text-[#F2F5F8] outline-none placeholder:text-[#506174] focus:border-[#1677E8]"
              />
            </div>
          </div>

          <div className="mt-5 flex gap-3">
            <button
              type="submit"
              className="bg-[#E50920] px-5 py-3 text-xs font-bold uppercase tracking-[0.15em] text-white transition hover:bg-[#FF1E32]"
            >
              Search Jobs
            </button>

            <button
              type="button"
              onClick={clearFilters}
              className="border border-[#1A3048] px-5 py-3 text-xs font-bold uppercase tracking-[0.15em] text-[#8D9AAA] transition hover:border-[#506174] hover:text-white"
            >
              Clear
            </button>
          </div>
        </form>

        {/* ERROR */}
        {error && (
          <div className="mb-6 border border-[#6B1A26] bg-[#18090D] p-4">
            <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#E50920]">
              DISCOVERY ERROR
            </div>

            <p className="mt-2 text-sm text-[#F2A0AA]">
              {error}
            </p>
          </div>
        )}

        {/* RESULTS HEADER */}
        <div className="mb-5 flex items-end justify-between">
          <div>
            <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-[#1677E8]">
              DISCOVERY RESULTS
            </div>

            <h2 className="mt-1 text-xl font-semibold">
              Available Opportunities
            </h2>
          </div>

          {!isPending && (
            <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#506174]">
              {results.totalJobs} RESULTS
            </div>
          )}
        </div>

        {/* LOADING */}
        {isPending && (
          <div className="border border-[#1A3048] bg-[#0B1626] p-12 text-center">
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#1677E8]">
              DISCOVERY ENGINE
            </div>

            <p className="mt-3 text-sm text-[#8D9AAA]">
              Loading available opportunities...
            </p>
          </div>
        )}

        {/* EMPTY */}
        {!isPending && !error && results.jobs.length === 0 && (
          <div className="border border-[#1A3048] bg-[#0B1626] p-12 text-center">
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#E50920]">
              NO MATCHING LISTINGS
            </div>

            <h3 className="mt-3 text-lg font-semibold">
              No jobs found
            </h3>

            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#8D9AAA]">
              Try changing your search criteria or clearing the filters.
            </p>
          </div>
        )}

        {/* JOB LIST */}
        {!isPending && results.jobs.length > 0 && (
          <div className="space-y-4">
            {results.jobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                match={matches[job.id]}
                isMatching={Boolean(matchingJobIds[job.id])}
                matchError={matchErrors[job.id]}
                onCalculateMatch={handleCalculateMatch}
              />
            ))}
          </div>
        )}

        {/* PAGINATION */}
        {!isPending && results.totalPages > 1 && (
          <div className="mt-8 flex items-center justify-center gap-5">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((current) => current - 1)}
              className="border border-[#1A3048] px-4 py-2 text-xs font-bold uppercase tracking-[0.12em] text-[#8D9AAA] transition hover:border-[#506174] hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
            >
              ← Previous
            </button>

            <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-[#506174]">
              Page {page} / {results.totalPages}
            </div>

            <button
              type="button"
              disabled={page >= results.totalPages}
              onClick={() => setPage((current) => current + 1)}
              className="border border-[#1A3048] px-4 py-2 text-xs font-bold uppercase tracking-[0.12em] text-[#8D9AAA] transition hover:border-[#506174] hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
function JobCard({
  job,
  match,
  isMatching,
  matchError,
  onCalculateMatch,
}: {
  job: Job;
  match?: JobMatchResult;
  isMatching: boolean;
  matchError?: string;
  onCalculateMatch: (jobId: string) => void;
}) {
  const visibleMatches = [
    ...(match?.must_have_matches ?? []),
    ...(match?.preferred_matches ?? []),
  ];

  const visibleGaps = [
    ...(match?.must_have_gaps ?? []),
    ...(match?.preferred_gaps ?? []),
  ];

  return (
    <article className="border border-[#1A3048] bg-[#0B1626] p-6 transition hover:border-[#29496A]">
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 flex-1">
            {/* JOB TITLE */}
            <h3 className="text-xl font-semibold tracking-tight text-[#F2F5F8]">
              {job.title}
            </h3>

            {/* COMPANY */}
            <p className="mt-2 text-sm font-medium text-[#8D9AAA]">
              {job.company || "Company not specified"}
            </p>

            {/* METADATA */}
            <div className="mt-4 flex flex-wrap gap-2">
              {job.location && <Tag>{job.location}</Tag>}

              {job.remote_type && (
                <Tag>{formatValue(job.remote_type)}</Tag>
              )}

              {job.employment_type && (
                <Tag>{formatValue(job.employment_type)}</Tag>
              )}
            </div>

            {/* SALARY */}
            {(job.salary_min !== null || job.salary_max !== null) && (
              <div className="mt-5">
                <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#506174]">
                  Compensation
                </div>

                <div className="mt-1 text-sm font-semibold text-[#F2F5F8]">
                  {formatSalary(job)}
                </div>
              </div>
            )}

            {/* DESCRIPTION */}
            {job.description && (
              <p className="mt-5 line-clamp-3 max-w-4xl text-sm leading-6 text-[#8D9AAA]">
                {job.description}
              </p>
            )}

            {/* SOURCE */}
            <div className="mt-5 flex items-center gap-2">
              <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#506174]">
                Source
              </span>

              <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#1677E8]">
                {job.source}
              </span>
            </div>
          </div>

          {/* ACTIONS */}
          <div className="flex shrink-0 gap-3 lg:flex-col">
            {job.source_url && (
              <a
                href={job.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="border border-[#1A3048] px-5 py-3 text-center text-xs font-bold uppercase tracking-[0.12em] text-[#8D9AAA] transition hover:border-[#1677E8] hover:text-white"
              >
                View Job
              </a>
            )}

            {job.application_url && (
              <a
                href={job.application_url}
                target="_blank"
                rel="noopener noreferrer"
                className="bg-[#E50920] px-5 py-3 text-center text-xs font-bold uppercase tracking-[0.12em] text-white transition hover:bg-[#FF1E32]"
              >
                Apply
              </a>
            )}
          </div>
        </div>

        {/* MATCH PANEL */}
        <div className="border-t border-[#1A3048] pt-5">
          <div className="grid gap-4 md:grid-cols-2">
            {/* JOB MATCH */}
            <div className="border border-[#1A3048] bg-[#05070A] p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-[#1677E8]">
                    Job Match
                  </div>

                  <div className="mt-2 text-3xl font-bold text-[#F2F5F8]">
                    {match ? `${Math.round(match.score)}%` : "—"}
                  </div>

                  {match && (
                    <div className="mt-1 font-mono text-[9px] uppercase tracking-[0.12em] text-[#506174]">
                      Confidence: {match.confidence}
                    </div>
                  )}
                </div>

                <button
                  type="button"
                  disabled={isMatching}
                  onClick={() => onCalculateMatch(job.id)}
                  className="border border-[#1A3048] px-4 py-2 text-[10px] font-bold uppercase tracking-[0.12em] text-[#8D9AAA] transition hover:border-[#1677E8] hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isMatching ? "Calculating..." : "Calculate Match"}
                </button>
              </div>

              {matchError && (
                <p className="mt-3 text-xs leading-5 text-[#F2A0AA]">
                  {matchError}
                </p>
              )}
            </div>

            {/* ATS READINESS */}
            <div className="border border-[#1A3048] bg-[#05070A] p-4">
              <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-[#1677E8]">
                ATS Readiness
              </div>

              <div className="mt-2 text-3xl font-bold text-[#506174]">
                Not calculated
              </div>

              <p className="mt-2 text-xs leading-5 text-[#506174]">
                ATS Readiness is a separate resume analysis and is not
                derived from Job Match.
              </p>
            </div>
          </div>

          {/* MATCH DETAILS */}
          {match && (
            <div className="mt-4 grid gap-4 lg:grid-cols-3">
              {/* MATCHING SKILLS */}
              <MatchList
                title="Matching Skills"
                items={visibleMatches.map((item) => ({
                  label: item.skill,
                  detail: formatEvidenceType(item.evidence_type),
                }))}
                emptyLabel="No matching skills identified."
              />

              {/* EXPERIENCE / STRENGTHS */}
              <MatchList
                title="Strengths"
                items={(match.strengths ?? []).map((strength) => ({
                  label: strength,
                }))}
                emptyLabel="No additional strengths identified."
              />

              {/* SKILL GAPS */}
              <MatchList
                title="Skill Gaps"
                items={visibleGaps.map((item) => ({
                  label: item.skill,
                  detail: formatEvidenceStatus(item.status),
                }))}
                emptyLabel="No skill gaps identified."
                warning
              />
            </div>
          )}

          {/* SCORE BREAKDOWN */}
          {match && match.components.length > 0 && (
            <div className="mt-4 border border-[#1A3048] bg-[#05070A] p-4">
              <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-[#1677E8]">
                Score Breakdown
              </div>

              <div className="mt-3 space-y-3">
                {match.components.map((component) => (
                  <div key={component.name}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-xs font-medium text-[#F2F5F8]">
                        {formatEvidenceType(component.name)}
                      </span>

                      <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-[#506174]">
                        {component.score} / {component.max_score}
                      </span>
                    </div>

                    <p className="mt-1 text-xs leading-5 text-[#506174]">
                      {component.explanation}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}
function MatchList({
  title,
  items,
  emptyLabel,
  warning = false,
}: {
  title: string;
  items: Array<{
    label: string;
    detail?: string;
  }>;
  emptyLabel: string;
  warning?: boolean;
}) {
  return (
    <div className="border border-[#1A3048] bg-[#05070A] p-4">
      <div
        className={`font-mono text-[9px] uppercase tracking-[0.15em] ${
          warning ? "text-[#E50920]" : "text-[#1677E8]"
        }`}
      >
        {title}
      </div>

      {items.length === 0 ? (
        <p className="mt-3 text-xs text-[#506174]">
          {emptyLabel}
        </p>
      ) : (
        <div className="mt-3 space-y-2">
          {items.slice(0, 6).map((item, index) => (
            <div
              key={`${item.label}-${index}`}
              className="flex items-start gap-2"
            >
              <span
                className={
                  warning
                    ? "mt-0.5 text-[#E50920]"
                    : "mt-0.5 text-[#1677E8]"
                }
              >
                {warning ? "⚠" : "✓"}
              </span>

              <div className="min-w-0">
                <div className="text-xs font-medium text-[#F2F5F8]">
                  {item.label}
                </div>

                {item.detail && (
                  <div className="mt-0.5 font-mono text-[8px] uppercase tracking-[0.1em] text-[#506174]">
                    {item.detail}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatEvidenceType(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatEvidenceStatus(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="border border-[#1A3048] bg-[#05070A] px-3 py-1.5 font-mono text-[9px] uppercase tracking-[0.1em] text-[#8D9AAA]">
      {children}
    </span>
  );
}

function formatValue(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatSalary(job: Job): string {
  const currency = job.salary_currency || "USD";

  if (job.salary_min !== null && job.salary_max !== null) {
    return `${currency} ${job.salary_min.toLocaleString()} – ${job.salary_max.toLocaleString()}`;
  }

  if (job.salary_min !== null) {
    return `From ${currency} ${job.salary_min.toLocaleString()}`;
  }

  if (job.salary_max !== null) {
    return `Up to ${currency} ${job.salary_max.toLocaleString()}`;
  }

  return "";
}