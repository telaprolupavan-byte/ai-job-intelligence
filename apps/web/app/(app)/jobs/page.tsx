"use client";

import { Suspense, useEffect, useState, useTransition } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Search as SearchIcon, SlidersHorizontal } from "lucide-react";
import {
  calculateAtsAlignment,
  calculateJobMatch,
  generateJobIntelligence,
  getJobEligibility,
  getJobs,
  type AtsAlignmentResult,
  type AtsAlignmentStatus,
  type AtsRequirementResult,
  type Job,
  type JobEligibilityResult,
  type JobIntelligenceData,
  type JobMatchResult,
} from "@/lib/jobs";
import Container from "@/components/app/container";
import Panel, { PanelHeader } from "@/components/app/panel";
import Badge from "@/components/app/badge";
import AppButton from "@/components/app/app-button";
import EmptyState from "@/components/app/empty-state";
import ErrorState from "@/components/app/error-state";
import { Skeleton } from "@/components/app/skeleton";

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

function filtersFromParams(params: URLSearchParams): JobFilters {
  return {
    search: params.get("search") ?? "",
    employmentType: params.get("employment_type") ?? "",
    remoteType: params.get("remote_type") ?? "",
    location: params.get("location") ?? "",
  };
}

function pageFromParams(params: URLSearchParams): number {
  const raw = Number(params.get("page"));
  return Number.isFinite(raw) && raw > 0 ? raw : 1;
}

function JobsPageInner() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const initialFilters = filtersFromParams(searchParams);
  const initialPage = pageFromParams(searchParams);

  // Draft state bound to the filter form inputs, not yet submitted.
  const [filterForm, setFilterForm] = useState<JobFilters>(initialFilters);

  // The filters actually applied to the last/current search request.
  const [appliedFilters, setAppliedFilters] =
    useState<JobFilters>(initialFilters);

  const [page, setPage] = useState(initialPage);
  const [results, setResults] = useState<JobResults>(EMPTY_RESULTS);
  const [error, setError] = useState<string | null>(null);
  const [matches, setMatches] = useState<Record<string, JobMatchResult>>({});

  // Keyed by job id so concurrent match requests for different jobs never
  // overwrite each other's loading/error state.
  const [matchingJobIds, setMatchingJobIds] = useState<
    Record<string, boolean>
  >({});
  const [matchErrors, setMatchErrors] = useState<Record<string, string>>({});
  const [intelligence, setIntelligence] = useState<
    Record<string, JobIntelligenceData>
  >({});
  const [intelligenceLoadingIds, setIntelligenceLoadingIds] = useState<
    Record<string, boolean>
  >({});
  const [intelligenceErrors, setIntelligenceErrors] = useState<
    Record<string, string>
  >({});
  const [eligibility, setEligibility] = useState<
    Record<string, JobEligibilityResult>
  >({});
  const [eligibilityLoadingIds, setEligibilityLoadingIds] = useState<
    Record<string, boolean>
  >({});
  const [eligibilityErrors, setEligibilityErrors] = useState<
    Record<string, string>
  >({});
  const [atsResults, setAtsResults] = useState<
    Record<string, AtsAlignmentResult>
  >({});
  const [atsLoadingIds, setAtsLoadingIds] = useState<Record<string, boolean>>(
    {},
  );
  const [atsErrors, setAtsErrors] = useState<Record<string, string>>({});
  const [isPending, startTransition] = useTransition();

  // Keeps the URL in sync with the active search so a refresh, a shared
  // link, or the browser's back/forward buttons land on the same results.
  useEffect(() => {
    const params = new URLSearchParams();

    if (appliedFilters.search) params.set("search", appliedFilters.search);
    if (appliedFilters.employmentType)
      params.set("employment_type", appliedFilters.employmentType);
    if (appliedFilters.remoteType)
      params.set("remote_type", appliedFilters.remoteType);
    if (appliedFilters.location)
      params.set("location", appliedFilters.location);
    if (page > 1) params.set("page", String(page));

    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, {
      scroll: false,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appliedFilters, page]);

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

  const activeFilterCount = Object.values(appliedFilters).filter(
    Boolean,
  ).length;

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

  async function handleCalculateAts(jobId: string) {
    setAtsLoadingIds((current) => ({ ...current, [jobId]: true }));
    setAtsErrors((current) => {
      const next = { ...current };
      delete next[jobId];
      return next;
    });

    try {
      const result = await calculateAtsAlignment(jobId);

      setAtsResults((current) => ({
        ...current,
        [jobId]: result,
      }));
    } catch (err) {
      console.error(err);

      setAtsErrors((current) => ({
        ...current,
        [jobId]:
          err instanceof Error
            ? err.message
            : "Unable to calculate ATS Alignment.",
      }));
    } finally {
      setAtsLoadingIds((current) => {
        const next = { ...current };
        delete next[jobId];
        return next;
      });
    }
  }

  async function handleCheckEligibility(jobId: string) {
    setEligibilityLoadingIds((current) => ({ ...current, [jobId]: true }));
    setEligibilityErrors((current) => {
      const next = { ...current };
      delete next[jobId];
      return next;
    });

    try {
      const result = await getJobEligibility(jobId);

      setEligibility((current) => ({
        ...current,
        [jobId]: result,
      }));
    } catch (err) {
      console.error(err);

      setEligibilityErrors((current) => ({
        ...current,
        [jobId]:
          err instanceof Error
            ? err.message
            : "Unable to check eligibility.",
      }));
    } finally {
      setEligibilityLoadingIds((current) => {
        const next = { ...current };
        delete next[jobId];
        return next;
      });
    }
  }

  async function handleViewIntelligence(jobId: string) {
    setIntelligenceLoadingIds((current) => ({ ...current, [jobId]: true }));
    setIntelligenceErrors((current) => {
      const next = { ...current };
      delete next[jobId];
      return next;
    });

    try {
      const response = await generateJobIntelligence(jobId);

      setIntelligence((current) => ({
        ...current,
        [jobId]: response.intelligence,
      }));
    } catch (err) {
      console.error(err);

      setIntelligenceErrors((current) => ({
        ...current,
        [jobId]:
          err instanceof Error
            ? err.message
            : "Unable to load Job Intelligence.",
      }));
    } finally {
      setIntelligenceLoadingIds((current) => {
        const next = { ...current };
        delete next[jobId];
        return next;
      });
    }
  }

  return (
    <div className="bg-app-bg text-app-text">
      <Container>
        {/* HEADER */}
        <div className="mb-6">
          <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-app-red">
            Intelligence Module
          </div>

          <div className="mt-2 flex flex-col justify-between gap-4 md:flex-row md:items-end">
            <div>
              <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight sm:text-3xl">
                Job Discovery
              </h1>

              <p className="mt-2 max-w-2xl text-sm leading-6 text-app-muted">
                Discover U.S. opportunities from connected job sources.
                Search, filter, and inspect available positions.
              </p>
            </div>

            <div className="rounded-lg border border-app-border bg-app-panel px-4 py-3">
              <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-app-blue">
                Active Listings
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
          className="mb-6 rounded-xl border border-app-border bg-app-panel"
        >
          <PanelHeader
              eyebrow="Search Parameters"
              description="Configure discovery criteria"
              action={
                <div className="hidden items-center gap-2 font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint md:flex">
                  <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
                  AJI / Discovery
                </div>
              }
            />

            <div className="grid gap-4 p-5 md:grid-cols-2 lg:grid-cols-4">
              <FilterField label="Role / Keyword" htmlFor="search">
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
                  className="w-full rounded-lg border border-app-border bg-app-bg px-3 py-3 text-sm text-app-text outline-none placeholder:text-app-faint focus:border-app-blue"
                />
              </FilterField>

              <FilterField label="Employment Type" htmlFor="employmentType">
                <select
                  id="employmentType"
                  value={filterForm.employmentType}
                  onChange={(event) =>
                    setFilterForm((current) => ({
                      ...current,
                      employmentType: event.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-app-border bg-app-bg px-3 py-3 text-sm text-app-text outline-none focus:border-app-blue"
                >
                  <option value="">All Types</option>
                  <option value="full_time">Full Time</option>
                  <option value="contract">Contract</option>
                  <option value="part_time">Part Time</option>
                  <option value="internship">Internship</option>
                  <option value="temporary">Temporary</option>
                </select>
              </FilterField>

              <FilterField label="Work Arrangement" htmlFor="remoteType">
                <select
                  id="remoteType"
                  value={filterForm.remoteType}
                  onChange={(event) =>
                    setFilterForm((current) => ({
                      ...current,
                      remoteType: event.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-app-border bg-app-bg px-3 py-3 text-sm text-app-text outline-none focus:border-app-blue"
                >
                  <option value="">All Arrangements</option>
                  <option value="remote">Remote</option>
                  <option value="hybrid">Hybrid</option>
                  <option value="onsite">On-site</option>
                </select>
              </FilterField>

              <FilterField label="Location" htmlFor="location">
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
                  className="w-full rounded-lg border border-app-border bg-app-bg px-3 py-3 text-sm text-app-text outline-none placeholder:text-app-faint focus:border-app-blue"
                />
              </FilterField>
            </div>

            <div className="flex flex-wrap items-center gap-3 px-5 pb-5">
              <AppButton type="submit">
                <SearchIcon className="h-3.5 w-3.5" aria-hidden="true" />
                Search Jobs
              </AppButton>

              <AppButton type="button" variant="ghost" onClick={clearFilters}>
                Clear{activeFilterCount > 0 ? ` (${activeFilterCount})` : ""}
              </AppButton>
            </div>
        </form>

        {/* ERROR */}
        {error && (
          <div className="mb-6">
            <ErrorState title="Discovery Error" message={error} />
          </div>
        )}

        {/* RESULTS HEADER */}
        <div className="mb-5 flex items-end justify-between">
          <div>
            <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-app-blue">
              Discovery Results
            </div>

            <h2 className="mt-1 text-xl font-semibold">
              Available Opportunities
            </h2>
          </div>

          {!isPending && (
            <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
              {results.totalJobs} Results
            </div>
          )}
        </div>

        {/* LOADING */}
        {isPending && (
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, index) => (
              <div
                key={index}
                className="rounded-xl border border-app-border bg-app-panel p-6"
              >
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="mt-3 h-3 w-1/3" />
                <div className="mt-4 flex gap-2">
                  <Skeleton className="h-6 w-20" />
                  <Skeleton className="h-6 w-24" />
                  <Skeleton className="h-6 w-16" />
                </div>
                <Skeleton className="mt-5 h-16 w-full" />
              </div>
            ))}
          </div>
        )}

        {/* EMPTY */}
        {!isPending && !error && results.jobs.length === 0 && (
          <EmptyState
            icon={SearchIcon}
            title="No jobs found"
            description="Try changing your search criteria or clearing the filters."
            action={
              activeFilterCount > 0 ? (
                <AppButton variant="secondary" onClick={clearFilters}>
                  Clear Filters
                </AppButton>
              ) : undefined
            }
          />
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
                intelligence={intelligence[job.id]}
                isLoadingIntelligence={Boolean(
                  intelligenceLoadingIds[job.id],
                )}
                intelligenceError={intelligenceErrors[job.id]}
                onViewIntelligence={handleViewIntelligence}
                eligibility={eligibility[job.id]}
                isCheckingEligibility={Boolean(
                  eligibilityLoadingIds[job.id],
                )}
                eligibilityError={eligibilityErrors[job.id]}
                onCheckEligibility={handleCheckEligibility}
                ats={atsResults[job.id]}
                isCalculatingAts={Boolean(atsLoadingIds[job.id])}
                atsError={atsErrors[job.id]}
                onCalculateAts={handleCalculateAts}
              />
            ))}
          </div>
        )}

        {/* PAGINATION */}
        {!isPending && results.totalPages > 1 && (
          <div className="mt-8 flex items-center justify-center gap-5">
            <AppButton
              variant="ghost"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((current) => current - 1)}
            >
              ← Previous
            </AppButton>

            <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-app-faint">
              Page {page} / {results.totalPages}
            </div>

            <AppButton
              variant="ghost"
              size="sm"
              disabled={page >= results.totalPages}
              onClick={() => setPage((current) => current + 1)}
            >
              Next →
            </AppButton>
          </div>
        )}
      </Container>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense
      fallback={
        <div className="bg-app-bg text-app-text">
          <Container>
            <Skeleton className="h-10 w-64" />
            <Skeleton className="mt-4 h-40 w-full" />
          </Container>
        </div>
      }
    >
      <JobsPageInner />
    </Suspense>
  );
}

function FilterField({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={htmlFor}
        className="mb-2 block font-mono text-[9px] uppercase tracking-[0.15em] text-app-muted"
      >
        {label}
      </label>

      {children}
    </div>
  );
}

function JobCard({
  job,
  match,
  isMatching,
  matchError,
  onCalculateMatch,
  intelligence,
  isLoadingIntelligence,
  intelligenceError,
  onViewIntelligence,
  eligibility,
  isCheckingEligibility,
  eligibilityError,
  onCheckEligibility,
  ats,
  isCalculatingAts,
  atsError,
  onCalculateAts,
}: {
  job: Job;
  match?: JobMatchResult;
  isMatching: boolean;
  matchError?: string;
  onCalculateMatch: (jobId: string) => void;
  intelligence?: JobIntelligenceData;
  isLoadingIntelligence: boolean;
  intelligenceError?: string;
  onViewIntelligence: (jobId: string) => void;
  eligibility?: JobEligibilityResult;
  isCheckingEligibility: boolean;
  eligibilityError?: string;
  onCheckEligibility: (jobId: string) => void;
  ats?: AtsAlignmentResult;
  isCalculatingAts: boolean;
  atsError?: string;
  onCalculateAts: (jobId: string) => void;
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
    <Panel as="article" padding="lg" interactive>
      <div className="flex flex-col gap-6">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 flex-1">
            {/* JOB TITLE */}
            <h3 className="text-xl font-semibold tracking-tight text-app-text">
              {job.title}
            </h3>

            {/* COMPANY */}
            <p className="mt-2 text-sm font-medium text-app-muted">
              {job.company || "Company not specified"}
            </p>

            {/* METADATA */}
            <div className="mt-4 flex flex-wrap gap-2">
              {job.location && <Badge>{job.location}</Badge>}
              {job.remote_type && <Badge>{formatValue(job.remote_type)}</Badge>}
              {job.employment_type && (
                <Badge>{formatValue(job.employment_type)}</Badge>
              )}
            </div>

            {/* SALARY */}
            {(job.salary_min !== null || job.salary_max !== null) && (
              <div className="mt-5">
                <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
                  Compensation
                </div>

                <div className="mt-1 text-sm font-semibold text-app-text">
                  {formatSalary(job)}
                </div>
              </div>
            )}

            {/* DESCRIPTION */}
            {job.description && (
              <p className="mt-5 line-clamp-3 max-w-4xl text-sm leading-6 text-app-muted">
                {job.description}
              </p>
            )}

            {/* SOURCE */}
            <div className="mt-5 flex items-center gap-2">
              <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
                Source
              </span>

              <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-blue">
                {job.source}
              </span>
            </div>
          </div>

          {/* ACTIONS */}
          <div className="flex shrink-0 gap-3 lg:flex-col">
            {job.source_url && (
              <AppButton
                variant="secondary"
                href={job.source_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                View Job
              </AppButton>
            )}

            {job.application_url && (
              <AppButton href={job.application_url} target="_blank" rel="noopener noreferrer">
                Apply
              </AppButton>
            )}
          </div>
        </div>

        {/* MATCH PANEL */}
        <div className="border-t border-app-border pt-5">
          {/* HARD ELIGIBILITY (AJI-011) */}
          <div className="mb-4 border border-app-border bg-app-bg p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-app-blue">
                  Hard Eligibility
                </div>
                <p className="mt-1 text-xs leading-5 text-app-dim">
                  Deterministic pre-filter against your configured hard
                  requirements (employment type, work arrangement,
                  location, work authorization, experience). Not a score
                  or AI match — see Job Match below for that.
                </p>
              </div>

              <div className="flex shrink-0 items-center gap-3">
                {eligibility && (
                  <Badge
                    tone={
                      eligibility.status === "eligible"
                        ? "blue"
                        : eligibility.status === "ineligible"
                          ? "danger"
                          : "neutral"
                    }
                  >
                    {formatValue(eligibility.status)}
                  </Badge>
                )}

                <AppButton
                  variant="ghost"
                  size="sm"
                  loading={isCheckingEligibility}
                  onClick={() => onCheckEligibility(job.id)}
                >
                  {isCheckingEligibility
                    ? "Checking..."
                    : eligibility
                      ? "Recheck"
                      : "Check Eligibility"}
                </AppButton>
              </div>
            </div>

            {eligibilityError && (
              <p className="mt-3 text-xs leading-5 text-app-danger-text">
                {eligibilityError}
              </p>
            )}

            {eligibility && (
              <EligibilityPanel result={eligibility} />
            )}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {/* JOB MATCH */}
            <div className="rounded-lg border border-app-border bg-app-bg p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-app-blue">
                    Job Match
                  </div>

                  <div className="mt-2 text-3xl font-bold text-app-text">
                    {match ? `${Math.round(match.score)}%` : "—"}
                  </div>

                  {match && (
                    <div className="mt-1 font-mono text-[9px] uppercase tracking-[0.12em] text-app-faint">
                      Confidence: {match.confidence}
                    </div>
                  )}
                </div>

                <AppButton
                  variant="ghost"
                  size="sm"
                  loading={isMatching}
                  onClick={() => onCalculateMatch(job.id)}
                >
                  {isMatching ? "Calculating..." : "Calculate Match"}
                </AppButton>
              </div>

              {matchError && (
                <p className="mt-3 text-xs leading-5 text-app-danger-text">
                  {matchError}
                </p>
              )}
            </div>

            {/* ATS ALIGNMENT (AJI-013) */}
            <div className="rounded-lg border border-app-border bg-app-bg p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-app-blue">
                    ATS Alignment
                  </div>

                  <div className="mt-2 text-3xl font-bold text-app-text">
                    {ats ? `${Math.round(ats.overall_score)}%` : "—"}
                  </div>

                  {ats && (
                    <div className="mt-1 font-mono text-[9px] uppercase tracking-[0.12em] text-app-faint">
                      Confidence: {ats.confidence}
                    </div>
                  )}
                </div>

                <AppButton
                  variant="ghost"
                  size="sm"
                  loading={isCalculatingAts}
                  onClick={() => onCalculateAts(job.id)}
                >
                  {isCalculatingAts
                    ? "Analyzing..."
                    : ats
                      ? "Recalculate"
                      : "Calculate ATS Alignment"}
                </AppButton>
              </div>

              <p className="mt-2 text-xs leading-5 text-app-faint">
                How well your resume demonstrates this JD&apos;s
                requirements — not a prediction of whether you&apos;ll get
                the job, and not derived from Job Match.
              </p>

              {atsError && (
                <p className="mt-3 text-xs leading-5 text-app-danger-text">
                  {atsError}
                </p>
              )}
            </div>
          </div>

          {/* ATS ALIGNMENT DETAILS */}
          {ats && <AtsAlignmentPanel result={ats} />}

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
            <div className="mt-4 rounded-lg border border-app-border bg-app-bg p-4">
              <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-blue">
                Score Breakdown
              </div>

              <div className="mt-3 space-y-3">
                {match.components.map((component) => (
                  <div key={component.name}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-xs font-medium text-app-text">
                        {formatEvidenceType(component.name)}
                      </span>

                      <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-app-faint">
                        {component.score} / {component.max_score}
                      </span>
                    </div>

                    <p className="mt-1 text-xs leading-5 text-app-faint">
                      {component.explanation}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* JOB INTELLIGENCE (AJI-012) */}
          <div className="mt-4 rounded-lg border border-app-border bg-app-bg p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-app-blue">
                  Job Intelligence
                </div>
                <p className="mt-1 text-xs leading-5 text-app-faint">
                  Structured, evidence-backed requirements extracted from
                  this JD. Not a score or a match — see Job Match above
                  for that.
                </p>
              </div>

              <AppButton
                variant="ghost"
                size="sm"
                loading={isLoadingIntelligence}
                onClick={() => onViewIntelligence(job.id)}
                className="shrink-0"
              >
                {isLoadingIntelligence
                  ? "Analyzing..."
                  : intelligence
                    ? "Refresh"
                    : "Analyze JD"}
              </AppButton>
            </div>

            {intelligenceError && (
              <p className="mt-3 text-xs leading-5 text-app-danger-text">
                {intelligenceError}
              </p>
            )}

            {intelligence && (
              <JobIntelligencePanel intelligence={intelligence} />
            )}
          </div>
        </div>
      </div>
    </Panel>
  );
}

function EligibilityPanel({ result }: { result: JobEligibilityResult }) {
  const flaggedChecks = result.checks.filter(
    (check) => check.status === "fail" || check.status === "unknown",
  );

  return (
    <div className="mt-3 space-y-2">
      {flaggedChecks.length === 0 ? (
        <p className="text-xs leading-5 text-app-dim">
          No configured hard requirement rules this job out.
        </p>
      ) : (
        flaggedChecks.map((check) => (
          <div key={check.constraint} className="flex items-start gap-2">
            <span
              aria-hidden="true"
              className={
                check.status === "fail"
                  ? "mt-0.5 text-app-red"
                  : "mt-0.5 text-app-dim"
              }
            >
              {check.status === "fail" ? "✕" : "?"}
            </span>

            <div className="min-w-0">
              <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-app-dim">
                {formatValue(check.constraint)}
              </div>
              <p className="text-xs leading-5 text-app-text">
                {check.reason}
              </p>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function JobIntelligencePanel({
  intelligence,
}: {
  intelligence: JobIntelligenceData;
}) {
  return (
    <div className="mt-4 grid gap-4 lg:grid-cols-2">
      <div className="rounded-lg border border-app-border p-3">
        <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
          Identity
        </div>
        <dl className="mt-2 space-y-1 text-xs text-app-text">
          <div>
            <dt className="inline text-app-faint">Normalized title: </dt>
            <dd className="inline">
              {intelligence.identity.normalized_title ?? "Unknown"}
            </dd>
          </div>
          <div>
            <dt className="inline text-app-faint">Role family: </dt>
            <dd className="inline">
              {intelligence.identity.role_family ?? "Unknown"}
            </dd>
          </div>
          <div>
            <dt className="inline text-app-faint">Seniority: </dt>
            <dd className="inline">
              {intelligence.identity.seniority ?? "Unknown"}
            </dd>
          </div>
          <div>
            <dt className="inline text-app-faint">Employment type: </dt>
            <dd className="inline">
              {formatValue(intelligence.employment.employment_type)}
            </dd>
          </div>
          <div>
            <dt className="inline text-app-faint">Domain: </dt>
            <dd className="inline">{intelligence.domain.value ?? "Unknown"}</dd>
          </div>
        </dl>
      </div>

      <div className="rounded-lg border border-app-border p-3">
        <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
          Location &amp; Authorization
        </div>
        <dl className="mt-2 space-y-1 text-xs text-app-text">
          <div>
            <dt className="inline text-app-faint">Arrangement: </dt>
            <dd className="inline">
              {formatValue(intelligence.location.remote_type)}
            </dd>
          </div>
          <div>
            <dt className="inline text-app-faint">Sponsorship: </dt>
            <dd className="inline">
              {formatValue(intelligence.authorization.sponsorship)}
            </dd>
          </div>
          <div>
            <dt className="inline text-app-faint">Citizenship: </dt>
            <dd className="inline">
              {formatValue(intelligence.authorization.citizenship)}
            </dd>
          </div>
          <div>
            <dt className="inline text-app-faint">Clearance: </dt>
            <dd className="inline">
              {formatValue(intelligence.authorization.clearance)}
            </dd>
          </div>
        </dl>
      </div>

      <RequirementList
        title="Required Skills"
        items={intelligence.required_skills.map((item) => ({
          label: item.canonical_skill,
          detail: item.evidence_text,
        }))}
        emptyLabel="No explicit required skills detected."
      />

      <RequirementList
        title="Preferred Skills"
        items={intelligence.preferred_skills.map((item) => ({
          label: item.canonical_skill,
          detail: item.evidence_text,
        }))}
        emptyLabel="No explicit preferred skills detected."
      />

      <RequirementList
        title="Required Experience"
        items={intelligence.required_experience.map((item) => ({
          label: `${item.minimum_years ?? "?"}+ years${
            item.area ? ` — ${item.area}` : ""
          }`,
          detail: item.evidence_text,
        }))}
        emptyLabel="No explicit years-of-experience requirements detected."
      />

      <RequirementList
        title="Responsibilities"
        items={intelligence.responsibilities.map((item) => ({
          label: item.description,
        }))}
        emptyLabel="No responsibilities detected."
      />
    </div>
  );
}

function AtsAlignmentPanel({ result }: { result: AtsAlignmentResult }) {
  const mustHave = result.requirement_results.filter(
    (item) => item.category === "must_have",
  );
  const preferred = result.requirement_results.filter(
    (item) => item.category === "preferred",
  );

  return (
    <div className="mt-4 rounded-lg border border-app-border bg-app-bg p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-blue">
          Requirement Alignment
        </div>
        <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-app-faint">
          Must-Have {result.must_have_matched}/{result.must_have_total} ·
          Preferred {result.preferred_matched}/{result.preferred_total}
        </div>
      </div>

      <div className="mt-3 grid gap-4 lg:grid-cols-2">
        <AtsRequirementGroup
          title="Must-Have Requirements"
          items={mustHave}
          emptyLabel="No must-have requirements detected."
        />
        <AtsRequirementGroup
          title="Preferred Requirements"
          items={preferred}
          emptyLabel="No preferred requirements detected."
        />
      </div>
    </div>
  );
}

function AtsRequirementGroup({
  title,
  items,
  emptyLabel,
}: {
  title: string;
  items: AtsRequirementResult[];
  emptyLabel: string;
}) {
  return (
    <div className="rounded-lg border border-app-border p-3">
      <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
        {title}
      </div>

      {items.length === 0 ? (
        <p className="mt-2 text-xs text-app-faint">{emptyLabel}</p>
      ) : (
        <ul className="mt-2 space-y-3">
          {items.map((item) => (
            <li key={item.requirement_id} className="text-xs">
              <div className="flex items-start gap-2">
                <span
                  aria-hidden="true"
                  className={`mt-0.5 ${atsStatusColor(item.status)}`}
                >
                  {atsStatusIcon(item.status)}
                </span>

                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-app-text">
                      {item.requirement_text}
                    </span>
                    <span className="font-mono text-[8px] uppercase tracking-[0.1em] text-app-faint">
                      {formatValue(item.status)}
                    </span>
                  </div>

                  <p className="mt-1 leading-5 text-app-faint">
                    {item.explanation}
                  </p>

                  {item.resume_evidence && (
                    <p className="mt-0.5 leading-5 text-app-dim">
                      {item.resume_evidence}
                    </p>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function atsStatusIcon(status: AtsAlignmentStatus): string {
  switch (status) {
    case "matched":
      return "✓";
    case "partial":
      return "◐";
    default:
      return "✕";
  }
}

function atsStatusColor(status: AtsAlignmentStatus): string {
  switch (status) {
    case "matched":
      return "text-app-blue";
    case "partial":
      return "text-app-dim";
    default:
      return "text-app-red";
  }
}

function RequirementList({
  title,
  items,
  emptyLabel,
}: {
  title: string;
  items: Array<{ label: string; detail?: string }>;
  emptyLabel: string;
}) {
  return (
    <div className="rounded-lg border border-app-border p-3">
      <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
        {title}
      </div>

      {items.length === 0 ? (
        <p className="mt-2 text-xs text-app-faint">{emptyLabel}</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {items.slice(0, 8).map((item, index) => (
            <li key={`${item.label}-${index}`} className="text-xs">
              <div className="font-medium text-app-text">{item.label}</div>
              {item.detail && (
                <div className="mt-0.5 text-app-faint">{item.detail}</div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
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
    <div className="rounded-lg border border-app-border bg-app-bg p-4">
      <div
        className={`font-mono text-[9px] uppercase tracking-[0.15em] ${
          warning ? "text-app-red" : "text-app-blue"
        }`}
      >
        {title}
      </div>

      {items.length === 0 ? (
        <p className="mt-3 text-xs text-app-faint">{emptyLabel}</p>
      ) : (
        <div className="mt-3 space-y-2">
          {items.slice(0, 6).map((item, index) => (
            <div
              key={`${item.label}-${index}`}
              className="flex items-start gap-2"
            >
              <span
                aria-hidden="true"
                className={warning ? "mt-0.5 text-app-red" : "mt-0.5 text-app-blue"}
              >
                {warning ? "⚠" : "✓"}
              </span>

              <div className="min-w-0">
                <div className="text-xs font-medium text-app-text">
                  {item.label}
                </div>

                {item.detail && (
                  <div className="mt-0.5 font-mono text-[8px] uppercase tracking-[0.1em] text-app-faint">
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
