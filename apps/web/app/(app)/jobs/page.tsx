"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
  useTransition,
} from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Search as SearchIcon, SlidersHorizontal } from "lucide-react";
import {
  calculateAtsAlignment,
  calculateGapAnalysis,
  calculateJobMatch,
  createResumeImprovement,
  generateJobIntelligence,
  getJob,
  getJobEligibility,
  getJobs,
  getLatestJobResults,
  runResumeImprovementRecheck,
  type AtsAlignmentResult,
  type AtsAlignmentStatus,
  type AtsRequirementResult,
  type GapAnalysisResult,
  type ImprovementDecisionInput,
  type Job,
  type JobEligibilityResult,
  type JobIntelligenceData,
  type JobMatchResult,
  type ResumeImprovementResult,
} from "@/lib/jobs";
import { getResumes, getResumeVersions } from "@/lib/resumes";
import {
  getDiscoveryStatus,
  type DiscoveryStatus,
} from "@/lib/job-discovery";
import {
  getApplications,
  removeSavedJob,
  saveJob,
  updateApplicationStatus,
  type Application,
} from "@/lib/applications";
import { ApiError } from "@/lib/api";
import {
  employmentTypeTone,
  formatEmploymentType,
  formatJobOrigin,
  formatValue,
} from "@/lib/job-format";
import {
  buildJobDecision,
  type NextStepKey,
  type StageKey,
} from "@/lib/job-decision";
import { getJobPriority, type JobPriorityResponse } from "@/lib/job-priority";
import { Bookmark, BookmarkCheck } from "lucide-react";
import Container from "@/components/app/container";
import Panel, { PanelHeader } from "@/components/app/panel";
import Badge from "@/components/app/badge";
import AppButton from "@/components/app/app-button";
import EmptyState from "@/components/app/empty-state";
import ErrorState from "@/components/app/error-state";
import { Skeleton } from "@/components/app/skeleton";
import ResumeVersionSelector, {
  type ResumeVersionOption,
} from "@/components/app/resume-version-selector";
import GapAnalysisSection from "@/components/app/gap-analysis-section";
import ResumeImprovementSection from "@/components/app/resume-improvement-section";
import JobDecisionPanel from "@/components/app/job-decision-panel";
import JobPriorityList, {
  type JobPriorityListStatus,
} from "@/components/app/job-priority-list";
import NeroErrorCard from "@/components/app/nero-error-card";

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

// AJI-025: "all" is the existing listing (unchanged, the default);
// "priority" is the user's analyzed jobs in priority order.
type JobsView = "all" | "priority";

function viewFromParams(params: URLSearchParams): JobsView {
  return params.get("view") === "priority" ? "priority" : "all";
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
  const [view, setView] = useState<JobsView>(() =>
    viewFromParams(searchParams),
  );

  // AJI-022: `?job=<id>` is where a successful job submission lands - that
  // one job's card, with its Job Intelligence loaded, instead of the
  // discovery list. Cleared by "All jobs".
  const [focusedJobId, setFocusedJobId] = useState<string | null>(
    searchParams.get("job"),
  );
  const [focusedJob, setFocusedJob] = useState<Job | null>(null);
  const [focusedJobError, setFocusedJobError] = useState<{
    message: string;
    // AJI-023: a 404 is final (the job doesn't exist, or it is another
    // user's private submission - the API makes the two identical), so it
    // gets no retry; anything else is transient and can be retried.
    notFound: boolean;
  } | null>(null);
  const [focusedJobReloadKey, setFocusedJobReloadKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  // AJI-024: null until loaded, and left null if the status call fails -
  // the page then simply shows no discovery-specific notices.
  const [discoveryStatus, setDiscoveryStatus] =
    useState<DiscoveryStatus | null>(null);
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
  // extraction_status per job ("complete" | "partial"), so the UI can say
  // when Job Intelligence is deterministic-only (no AI provider result).
  const [intelligenceStatuses, setIntelligenceStatuses] = useState<
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
  const [gapAnalyses, setGapAnalyses] = useState<
    Record<string, GapAnalysisResult>
  >({});
  const [gapAnalysisLoadingIds, setGapAnalysisLoadingIds] = useState<
    Record<string, boolean>
  >({});
  const [gapAnalysisErrors, setGapAnalysisErrors] = useState<
    Record<string, string>
  >({});
  const [improvements, setImprovements] = useState<
    Record<string, ResumeImprovementResult>
  >({});
  const [improvementSubmittingIds, setImprovementSubmittingIds] = useState<
    Record<string, boolean>
  >({});
  const [improvementRecheckingIds, setImprovementRecheckingIds] = useState<
    Record<string, boolean>
  >({});
  const [improvementErrors, setImprovementErrors] = useState<
    Record<string, string>
  >({});

  // AJI-019: the ONE page-level source of truth for which ResumeVersion
  // Job Match, ATS Alignment, and Gap Analysis all use. null means the
  // user hasn't made an explicit choice yet - resume_version_id stays
  // omitted from every request and the backend's existing default
  // (most recent Resume, preferring its master ResumeVersion) applies
  // exactly as it did before this feature existed.
  const [selectedResumeVersionId, setSelectedResumeVersionId] = useState<
    string | null
  >(null);
  const [resumeVersionState, setResumeVersionState] = useState<{
    status: "loading" | "error" | "empty" | "ready";
    options: ResumeVersionOption[];
    defaultOptionId: string | null;
    error?: string;
  }>({ status: "loading", options: [], defaultOptionId: null });

  const loadResumeVersions = useCallback(() => {
    let cancelled = false;

    setResumeVersionState((current) => ({ ...current, status: "loading" }));

    (async () => {
      try {
        const resumes = await getResumes();

        if (cancelled) return;

        if (resumes.length === 0) {
          setResumeVersionState({
            status: "empty",
            options: [],
            defaultOptionId: null,
          });
          return;
        }

        const versionsByResume = await Promise.all(
          resumes.map((resume) => getResumeVersions(resume.id)),
        );

        if (cancelled) return;

        const options: ResumeVersionOption[] = [];

        resumes.forEach((resume, index) => {
          for (const version of versionsByResume[index] ?? []) {
            options.push({
              id: version.id,
              resumeName: resume.filename,
              versionName: version.name,
              isMaster: version.is_master,
              createdAt: version.created_at,
            });
          }
        });

        // resumes[0] is the most recently created Resume (the API
        // already returns them sorted that way) - mirrors the same
        // default resolution Job Match/ATS/Gap Analysis apply
        // server-side when resume_version_id is omitted, purely for
        // display before the user picks anything explicitly.
        const defaultResumeVersions = versionsByResume[0] ?? [];
        const defaultVersion =
          defaultResumeVersions.find((version) => version.is_master) ??
          defaultResumeVersions[0] ??
          null;

        setResumeVersionState({
          status: options.length === 0 ? "empty" : "ready",
          options,
          defaultOptionId: defaultVersion ? defaultVersion.id : null,
        });
      } catch (err) {
        if (cancelled) return;

        setResumeVersionState({
          status: "error",
          options: [],
          defaultOptionId: null,
          error:
            err instanceof Error
              ? err.message
              : "Unable to load your resume versions.",
        });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return loadResumeVersions();
  }, [loadResumeVersions]);

  // This user's existing saved/applied tracking record for each job,
  // keyed by job id (not by application id) - looked up once so the
  // Jobs list can show persisted "Saved"/"Applied" state rather than
  // resetting on every reload.
  const [applicationsByJobId, setApplicationsByJobId] = useState<
    Record<string, Application>
  >({});
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
    if (view === "priority") params.set("view", "priority");
    if (focusedJobId) params.set("job", focusedJobId);

    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, {
      scroll: false,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appliedFilters, page, view, focusedJobId]);

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

  useEffect(() => {
    let cancelled = false;

    getDiscoveryStatus()
      .then((status) => {
        if (!cancelled) setDiscoveryStatus(status);
      })
      .catch(() => {
        if (!cancelled) setDiscoveryStatus(null);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!focusedJobId) {
      setFocusedJob(null);
      setFocusedJobError(null);
      return;
    }

    let cancelled = false;

    setFocusedJob(null);
    setFocusedJobError(null);

    getJob(focusedJobId)
      .then((job) => {
        if (cancelled) return;

        setFocusedJob(job);
        setFocusedJobError(null);
        // Reuses the snapshot the submission just created (the POST is
        // idempotent), so this renders the job's understanding, not a
        // second analysis.
        handleViewIntelligence(job.id);
        // AJI-023: Hard Eligibility is deterministic and resume-free, so
        // the opened job shows it straight away.
        handleCheckEligibility(job.id);
      })
      .catch((err) => {
        if (cancelled) return;

        console.error(err);
        setFocusedJob(null);
        setFocusedJobError({
          message:
            err instanceof Error ? err.message : "Unable to load this job.",
          notFound: err instanceof ApiError && err.status === 404,
        });
      });

    return () => {
      cancelled = true;
    };
  }, [focusedJobId, focusedJobReloadKey]);

  // AJI-023: the ResumeVersion the resume-based results are shown for -
  // the explicit selection, else the default the selector displays. The
  // saved-results read is pinned to it, so the page never shows a result
  // from a version other than the one the selector names.
  const effectiveResumeVersionId =
    selectedResumeVersionId ?? resumeVersionState.defaultOptionId;

  // AJI-025: the Priority view. Pinned to the ResumeVersion the selector
  // shows, scoped by the same filters as the listing, and refetched every
  // time the view is shown again - including on return from a job where
  // Match or ATS was just calculated - so it never shows an order built
  // from results that have since changed. Keyed like savedResults below,
  // so a late response for an old key is never shown.
  const [priorityPage, setPriorityPage] = useState(1);
  const [priorityReloadKey, setPriorityReloadKey] = useState(0);
  const [priorityFetch, setPriorityFetch] = useState<{
    key: string | null;
    loading: boolean;
    result: JobPriorityResponse | null;
    error: string | null;
  }>({ key: null, loading: false, result: null, error: null });

  const priorityKey =
    view === "priority" && !focusedJobId && resumeVersionState.status === "ready"
      ? JSON.stringify([
          effectiveResumeVersionId,
          appliedFilters,
          priorityPage,
          priorityReloadKey,
        ])
      : null;

  useEffect(() => {
    if (priorityKey === null) return;

    let cancelled = false;
    const key = priorityKey;

    setPriorityFetch({ key, loading: true, result: null, error: null });

    getJobPriority({
      resumeVersionId: effectiveResumeVersionId ?? undefined,
      search: appliedFilters.search || undefined,
      employment_type: appliedFilters.employmentType || undefined,
      remote_type: appliedFilters.remoteType || undefined,
      location: appliedFilters.location || undefined,
      page: priorityPage,
      page_size: 20,
    })
      .then((result) => {
        if (cancelled) return;
        setPriorityFetch({ key, loading: false, result, error: null });
      })
      .catch((err) => {
        if (cancelled) return;
        console.error(err);
        setPriorityFetch({
          key,
          loading: false,
          result: null,
          error:
            err instanceof Error ? err.message : "Unable to load job priority.",
        });
      });

    return () => {
      cancelled = true;
    };
    // priorityKey already encodes every input this request reads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [priorityKey]);

  let priorityStatus: JobPriorityListStatus;
  let priorityError: string | null = null;

  if (resumeVersionState.status === "loading") {
    priorityStatus = "loading";
  } else if (resumeVersionState.status === "empty") {
    priorityStatus = "no_resume";
  } else if (resumeVersionState.status === "error") {
    priorityStatus = "error";
    priorityError =
      "Your resume versions couldn't be loaded, so priority can't be tied to one. Please try again.";
  } else if (priorityFetch.key !== priorityKey || priorityFetch.loading) {
    priorityStatus = "loading";
  } else if (priorityFetch.error) {
    priorityStatus = "error";
    priorityError = priorityFetch.error;
  } else {
    priorityStatus = "ready";
  }

  function retryPriority() {
    if (resumeVersionState.status === "error") {
      loadResumeVersions();
      return;
    }
    setPriorityReloadKey((key) => key + 1);
  }

  function selectResumeVersion(id: string | null) {
    setSelectedResumeVersionId(id);
    setPriorityPage(1);
  }

  const [savedResults, setSavedResults] = useState<{
    key: string | null;
    loading: boolean;
    error: string | null;
  }>({ key: null, loading: false, error: null });
  const [savedResultsReloadKey, setSavedResultsReloadKey] = useState(0);

  // AJI-023: opening a job shows its existing Job Match, ATS Alignment,
  // Gap Analysis and Resume Improvement for that version (read-only GETs,
  // nothing recalculated). "Nothing saved yet" is a normal outcome, shown
  // as each stage's not-yet-run state. A result the user produced in this
  // session is never overwritten by the read.
  useEffect(() => {
    const jobId = focusedJob?.id;

    if (
      !jobId ||
      resumeVersionState.status !== "ready" ||
      !effectiveResumeVersionId
    ) {
      return;
    }

    let cancelled = false;
    const key = `${jobId}:${effectiveResumeVersionId}`;

    setSavedResults({ key, loading: true, error: null });

    getLatestJobResults(jobId, effectiveResumeVersionId)
      .then((latest) => {
        if (cancelled) return;

        const keepExisting = <T,>(
          current: Record<string, T>,
          value: T | null,
        ): Record<string, T> =>
          value === null || current[jobId] !== undefined
            ? current
            : { ...current, [jobId]: value };

        setMatches((current) => keepExisting(current, latest.match));
        setAtsResults((current) => keepExisting(current, latest.ats));
        setGapAnalyses((current) => keepExisting(current, latest.gapAnalysis));
        // An improvement is only meaningful next to the Gap Analysis it
        // was approved from; otherwise the section starts from review.
        if (
          latest.improvement &&
          latest.gapAnalysis &&
          latest.improvement.gap_analysis_id === latest.gapAnalysis.id
        ) {
          setImprovements((current) =>
            keepExisting(current, latest.improvement),
          );
        }

        setSavedResults({ key, loading: false, error: null });
      })
      .catch((err) => {
        if (cancelled) return;

        console.error(err);
        setSavedResults({
          key,
          loading: false,
          error:
            err instanceof Error
              ? err.message
              : "Unable to load your saved results.",
        });
      });

    return () => {
      cancelled = true;
    };
  }, [
    focusedJob?.id,
    resumeVersionState.status,
    effectiveResumeVersionId,
    savedResultsReloadKey,
  ]);

  // Loaded once (not per-page/filter): this is the user's own tracking
  // state, independent of which page of job results is showing.
  useEffect(() => {
    let cancelled = false;

    getApplications()
      .then((applications) => {
        if (cancelled) return;

        setApplicationsByJobId(
          Object.fromEntries(
            applications.map((application) => [
              application.job.id,
              application,
            ]),
          ),
        );
      })
      .catch(() => {
        // Not fatal to browsing jobs - Save/Mark as Applied will simply
        // start from an untracked state if this fails.
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const applicationStatusByJobId = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(applicationsByJobId).map(([jobId, application]) => [
          jobId,
          application.status,
        ]),
      ),
    [applicationsByJobId],
  );

  function handleApplicationChange(
    jobId: string,
    application: Application | null,
  ) {
    setApplicationsByJobId((current) => {
      const next = { ...current };
      if (application) {
        next[jobId] = application;
      } else {
        delete next[jobId];
      }
      return next;
    });
  }

  function handleSearch(event: React.FormEvent) {
    event.preventDefault();
    setAppliedFilters(filterForm);
    setPage(1);
    setPriorityPage(1);
  }

  function clearFilters() {
    setFilterForm(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
    setPage(1);
    setPriorityPage(1);
  }

  const activeFilterCount = Object.values(appliedFilters).filter(
    Boolean,
  ).length;

  // Job Match, ATS Alignment and Gap Analysis are all computed against
  // one exact ResumeVersion, so a result produced for the previously
  // selected version says nothing about the newly selected one. Keeping
  // it on screen would show a score/gap list from another resume under
  // the new selection with nothing marking it stale - the one thing
  // AJI-019's single shared selectedResumeVersionId exists to prevent.
  // Dropping it returns each panel to its un-calculated state, matching
  // the selector's own "applies to the next intelligence calculation".
  //
  // Hard Eligibility and Job Intelligence are deliberately NOT cleared:
  // neither reads the resume (eligibility is profile/preferences vs.
  // job, Job Intelligence is job-only shared data), so switching resume
  // version cannot change either one.
  useEffect(() => {
    // Returning the same reference when there is nothing to drop lets
    // React bail out instead of re-rendering on mount.
    const dropAll = <T,>(current: Record<string, T>): Record<string, T> =>
      Object.keys(current).length === 0 ? current : {};

    setMatches(dropAll);
    setMatchErrors(dropAll);
    setAtsResults(dropAll);
    setAtsErrors(dropAll);
    setGapAnalyses(dropAll);
    setGapAnalysisErrors(dropAll);
  }, [selectedResumeVersionId]);

  async function handleCalculateMatch(jobId: string) {
    setMatchingJobIds((current) => ({ ...current, [jobId]: true }));
    setMatchErrors((current) => {
      const next = { ...current };
      delete next[jobId];
      return next;
    });

    try {
      const match = await calculateJobMatch(
        jobId,
        selectedResumeVersionId ?? undefined,
      );

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
      const result = await calculateAtsAlignment(
        jobId,
        selectedResumeVersionId ?? undefined,
      );

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

  async function handleCalculateGapAnalysis(jobId: string) {
    setGapAnalysisLoadingIds((current) => ({ ...current, [jobId]: true }));
    setGapAnalysisErrors((current) => {
      const next = { ...current };
      delete next[jobId];
      return next;
    });

    try {
      const result = await calculateGapAnalysis(
        jobId,
        selectedResumeVersionId ?? undefined,
      );

      setGapAnalyses((current) => ({
        ...current,
        [jobId]: result,
      }));
    } catch (err) {
      console.error(err);

      setGapAnalysisErrors((current) => ({
        ...current,
        [jobId]:
          err instanceof Error
            ? err.message
            : "Unable to load Gap Analysis.",
      }));
    } finally {
      setGapAnalysisLoadingIds((current) => {
        const next = { ...current };
        delete next[jobId];
        return next;
      });
    }
  }

  // AJI-021 — the user's approved improvements for a job. The request
  // body carries only the decisions; which ResumeVersion is improved
  // comes from the Gap Analysis record server-side, so this never needs
  // to (and never should) re-assert the selected version itself.
  async function handleApproveImprovements(
    jobId: string,
    gapAnalysisId: string,
    decisions: ImprovementDecisionInput[],
  ) {
    setImprovementSubmittingIds((current) => ({ ...current, [jobId]: true }));
    setImprovementErrors((current) => {
      const next = { ...current };
      delete next[jobId];
      return next;
    });

    try {
      const result = await createResumeImprovement(
        jobId,
        gapAnalysisId,
        decisions,
      );

      setImprovements((current) => ({ ...current, [jobId]: result }));
    } catch (err) {
      console.error(err);

      setImprovementErrors((current) => ({
        ...current,
        [jobId]:
          err instanceof Error
            ? err.message
            : "Unable to apply your approved improvements.",
      }));
    } finally {
      setImprovementSubmittingIds((current) => {
        const next = { ...current };
        delete next[jobId];
        return next;
      });
    }
  }

  async function handleRunRecheck(jobId: string, improvementId: string) {
    setImprovementRecheckingIds((current) => ({ ...current, [jobId]: true }));
    setImprovementErrors((current) => {
      const next = { ...current };
      delete next[jobId];
      return next;
    });

    try {
      const result = await runResumeImprovementRecheck(
        jobId,
        improvementId,
      );

      setImprovements((current) => ({ ...current, [jobId]: result }));
    } catch (err) {
      console.error(err);

      setImprovementErrors((current) => ({
        ...current,
        [jobId]:
          err instanceof Error
            ? err.message
            : "Unable to recheck your new version.",
      }));
    } finally {
      setImprovementRecheckingIds((current) => {
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
      setIntelligenceStatuses((current) => ({
        ...current,
        [jobId]: response.extraction_status,
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

  function renderJobCard(job: Job, focused = false) {
    return (
      <JobCard
        key={job.id}
        job={job}
        application={applicationsByJobId[job.id]}
        onApplicationChange={handleApplicationChange}
        onOpen={focused ? undefined : openJob}
        hideTracking={focused}
        intelligenceStatus={intelligenceStatuses[job.id]}
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
        gapAnalysis={gapAnalyses[job.id]}
        isCalculatingGapAnalysis={Boolean(
          gapAnalysisLoadingIds[job.id],
        )}
        gapAnalysisError={gapAnalysisErrors[job.id]}
        onCalculateGapAnalysis={handleCalculateGapAnalysis}
        improvement={improvements[job.id]}
        isSubmittingImprovement={Boolean(
          improvementSubmittingIds[job.id],
        )}
        isRecheckingImprovement={Boolean(
          improvementRecheckingIds[job.id],
        )}
        improvementError={improvementErrors[job.id]}
        onApproveImprovements={handleApproveImprovements}
        onRunRecheck={handleRunRecheck}
      />
    );
  }

  function showAllJobs() {
    setFocusedJobId(null);
  }

  // AJI-023: a job's full workflow view - the same `?job=<id>` view a
  // submitted job lands on (AJI-022), now reachable from any card.
  function openJob(jobId: string) {
    setFocusedJobId(jobId);
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0 });
    }
  }

  const focusedJobKey = focusedJob
    ? `${focusedJob.id}:${effectiveResumeVersionId ?? ""}`
    : null;
  const savedResultsLoading =
    savedResults.loading && savedResults.key === focusedJobKey;
  const savedResultsError =
    savedResults.key === focusedJobKey ? savedResults.error : null;

  const focusedDecision = useMemo(() => {
    if (!focusedJob) return null;

    const id = focusedJob.id;
    const gapAnalysis = gapAnalyses[id];
    const improvement = improvements[id];

    return buildJobDecision({
      resume: resumeVersionState.status,
      savedResultsLoading,
      intelligence: intelligence[id],
      intelligenceStatus: intelligenceStatuses[id],
      intelligenceLoading: Boolean(intelligenceLoadingIds[id]),
      intelligenceError: intelligenceErrors[id],
      eligibility: eligibility[id],
      eligibilityLoading: Boolean(eligibilityLoadingIds[id]),
      eligibilityError: eligibilityErrors[id],
      match: matches[id],
      matchLoading: Boolean(matchingJobIds[id]),
      matchError: matchErrors[id],
      ats: atsResults[id],
      atsLoading: Boolean(atsLoadingIds[id]),
      atsError: atsErrors[id],
      gapAnalysis,
      gapLoading: Boolean(gapAnalysisLoadingIds[id]),
      gapError: gapAnalysisErrors[id],
      // Only the improvement approved from the Gap Analysis on screen
      // belongs to this resume version's workflow.
      improvement:
        improvement && gapAnalysis && improvement.gap_analysis_id === gapAnalysis.id
          ? improvement
          : undefined,
      improvementLoading: Boolean(
        improvementSubmittingIds[id] || improvementRecheckingIds[id],
      ),
      improvementError: improvementErrors[id],
      application: applicationsByJobId[id],
    });
  }, [
    focusedJob,
    resumeVersionState.status,
    savedResultsLoading,
    intelligence,
    intelligenceStatuses,
    intelligenceLoadingIds,
    intelligenceErrors,
    eligibility,
    eligibilityLoadingIds,
    eligibilityErrors,
    matches,
    matchingJobIds,
    matchErrors,
    atsResults,
    atsLoadingIds,
    atsErrors,
    gapAnalyses,
    gapAnalysisLoadingIds,
    gapAnalysisErrors,
    improvements,
    improvementSubmittingIds,
    improvementRecheckingIds,
    improvementErrors,
    applicationsByJobId,
  ]);

  const effectiveResumeVersion = resumeVersionState.options.find(
    (option) => option.id === effectiveResumeVersionId,
  );
  const effectiveResumeVersionLabel = effectiveResumeVersion
    ? `${effectiveResumeVersion.versionName} (${effectiveResumeVersion.resumeName})`
    : null;

  function runStage(jobId: string, key: StageKey) {
    switch (key) {
      case "intelligence":
        return handleViewIntelligence(jobId);
      case "eligibility":
        return handleCheckEligibility(jobId);
      case "match":
        return handleCalculateMatch(jobId);
      case "ats":
        return handleCalculateAts(jobId);
      case "gap":
        return handleCalculateGapAnalysis(jobId);
      default:
        return undefined;
    }
  }

  function runNextStep(jobId: string, key: NextStepKey) {
    switch (key) {
      case "analyze_job":
        return runStage(jobId, "intelligence");
      case "check_eligibility":
        return runStage(jobId, "eligibility");
      case "calculate_match":
        return runStage(jobId, "match");
      case "calculate_ats":
        return runStage(jobId, "ats");
      case "analyze_gaps":
        return runStage(jobId, "gap");
      case "review_improvements":
        document
          .getElementById(`resume-improvement-${jobId}`)
          ?.scrollIntoView({ behavior: "smooth", block: "start" });
        return undefined;
      default:
        return undefined;
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

            <div className="flex flex-wrap items-end gap-4">
              {/* AJI-022 entry point (Figma 133:266 / 133:267) */}
              <AppButton
                href="/jobs/submit"
                className="h-12 w-[180px] rounded-[10px] text-[13px] normal-case tracking-normal text-app-text"
              >
                Add a job
              </AppButton>

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
        </div>

        {/* FILTER PANEL */}
        {!focusedJobId && (
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
        )}

        {/* ERROR */}
        {error && (
          <div className="mb-6">
            <ErrorState title="Discovery Error" message={error} />
          </div>
        )}

        {/* DISCOVERY NOTICES (AJI-024) */}
        {discoveryStatus?.test_mode && (
          <div
            role="note"
            className="mb-6 flex flex-col gap-2 rounded-lg border border-app-danger-border bg-app-danger-bg px-4 py-3 sm:flex-row sm:items-center sm:gap-3"
          >
            <Badge tone="danger" className="self-start sm:self-auto">
              Test data
            </Badge>
            <p className="text-xs leading-5 text-app-danger-text">
              Development test mode is on. Jobs marked Test data come from
              NERO&apos;s synthetic fixture provider and are not real
              postings.
            </p>
          </div>
        )}

        {!error && discoveryStatus?.last_run?.status === "failed" && (
          <p
            role="status"
            className="mb-6 rounded-lg border border-app-border bg-app-panel px-4 py-3 text-xs leading-5 text-app-muted"
          >
            The most recent job discovery run did not complete. Showing
            the jobs discovered before it.
          </p>
        )}

        {/* RESULTS TOOLBAR (selector placement per AJI-019 — Jobs Placement Reference) */}
        <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          {focusedJobId ? (
            <div>
              <AppButton variant="ghost" size="sm" onClick={showAllJobs}>
                ← All jobs
              </AppButton>
            </div>
          ) : (
            <div className="min-w-0">
              <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-app-blue">
                Discovery Results
              </div>

              <h2 className="mt-1 text-xl font-semibold">
                {view === "priority"
                  ? "Your Priority Order"
                  : "Available Opportunities"}
              </h2>

              {view === "all" && !isPending && (
                <p className="mt-1 text-xs text-app-faint">
                  {results.totalJobs} results · Resume choice applies to the
                  next intelligence calculation.
                </p>
              )}

              {view === "priority" && (
                <p className="mt-1 text-xs text-app-faint">
                  The jobs you&apos;ve analyzed, ordered for your attention ·
                  Resume choice changes the order.
                </p>
              )}

              {/* AJI-025: the listing stays the default; Priority is opt-in. */}
              <div
                role="group"
                aria-label="Jobs view"
                className="mt-3 inline-flex rounded-lg border border-app-border bg-app-panel p-1"
              >
                {(
                  [
                    ["all", "All jobs"],
                    ["priority", "Priority order"],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    aria-pressed={view === key}
                    onClick={() => setView(key)}
                    className={
                      view === key
                        ? "rounded-md bg-app-blue-soft px-3 py-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-app-blue"
                        : "rounded-md px-3 py-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-app-muted hover:text-app-text"
                    }
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <ResumeVersionSelector
            status={resumeVersionState.status}
            options={resumeVersionState.options}
            defaultOptionId={resumeVersionState.defaultOptionId}
            selectedId={selectedResumeVersionId}
            onSelect={selectResumeVersion}
            onRetry={loadResumeVersions}
          />
        </div>

        {/* SUBMITTED / FOCUSED JOB (AJI-022, AJI-023) */}
        {focusedJobId && focusedJobError?.notFound && (
          <div className="space-y-4">
            <NeroErrorCard
              title="Job unavailable"
              message="This job doesn't exist or isn't available to your account. Jobs you add stay private to you."
            />
            <AppButton variant="secondary" size="sm" onClick={showAllJobs}>
              Back to all jobs
            </AppButton>
          </div>
        )}

        {focusedJobId && focusedJobError && !focusedJobError.notFound && (
          <ErrorState
            title="Job unavailable"
            message={focusedJobError.message}
            onRetry={() => setFocusedJobReloadKey((key) => key + 1)}
          />
        )}

        {focusedJobId && !focusedJobError && !focusedJob && (
          <div className="rounded-xl border border-app-border bg-app-panel p-6">
            <Skeleton className="h-5 w-2/3" />
            <Skeleton className="mt-3 h-3 w-1/3" />
            <Skeleton className="mt-5 h-16 w-full" />
          </div>
        )}

        {focusedJobId && focusedJob && focusedDecision && (
          <JobDecisionPanel
            jobId={focusedJob.id}
            decision={focusedDecision}
            resumeVersionLabel={
              resumeVersionState.status === "ready"
                ? effectiveResumeVersionLabel
                : null
            }
            savedResultsError={savedResultsError}
            onRetrySavedResults={() =>
              setSavedResultsReloadKey((key) => key + 1)
            }
            onRunStage={(key) => runStage(focusedJob.id, key)}
            onNextStep={(key) => runNextStep(focusedJob.id, key)}
            trackingActions={
              <div className="flex flex-wrap items-start gap-3 sm:flex-col sm:items-end">
                <JobTrackingActions
                  jobId={focusedJob.id}
                  application={applicationsByJobId[focusedJob.id]}
                  onApplicationChange={handleApplicationChange}
                />
                {focusedJob.application_url && (
                  <AppButton
                    variant="ghost"
                    size="sm"
                    href={focusedJob.application_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Apply on employer site
                  </AppButton>
                )}
              </div>
            }
          />
        )}

        {focusedJobId && focusedJob && renderJobCard(focusedJob, true)}

        {/* PRIORITY VIEW (AJI-025) */}
        {!focusedJobId && view === "priority" && (
          <JobPriorityList
            status={priorityStatus}
            result={priorityFetch.result}
            error={priorityError}
            onRetry={retryPriority}
            onOpenJob={openJob}
            onPageChange={setPriorityPage}
            applicationStatusByJobId={applicationStatusByJobId}
          />
        )}

        {/* LOADING */}
        {!focusedJobId && view === "all" && isPending && (
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

        {/* EMPTY — no discovery source connected (AJI-024) */}
        {!focusedJobId &&
          view === "all" &&
          !isPending &&
          !error &&
          results.jobs.length === 0 &&
          activeFilterCount === 0 &&
          discoveryStatus?.source_configured === false && (
            <EmptyState
              icon={SearchIcon}
              title="No job source connected yet"
              description="Job discovery isn't connected to a job provider yet, so there are no discovered jobs to show. You can still add a job you found yourself and run the full NERO analysis on it."
              action={
                <AppButton href="/jobs/submit" variant="secondary">
                  Add a job
                </AppButton>
              }
            />
          )}

        {/* EMPTY */}
        {!focusedJobId &&
          view === "all" &&
          !isPending &&
          !error &&
          results.jobs.length === 0 &&
          !(
            activeFilterCount === 0 &&
            discoveryStatus?.source_configured === false
          ) && (
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
        {!focusedJobId && view === "all" && !isPending && results.jobs.length > 0 && (
          <div className="space-y-4">
            {results.jobs.map((job) => renderJobCard(job))}
          </div>
        )}

        {/* PAGINATION */}
        {!focusedJobId && view === "all" && !isPending && results.totalPages > 1 && (
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

function formatApplicationStatus(status: string): string {
  return status
    .split("_")
    .map((word) => word[0]?.toUpperCase() + word.slice(1))
    .join(" ");
}

function JobTrackingActions({
  jobId,
  application,
  onApplicationChange,
}: {
  jobId: string;
  application?: Application;
  onApplicationChange: (jobId: string, application: Application | null) => void;
}) {
  const [pending, setPending] = useState<"save" | "apply" | "remove" | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setPending("save");
    setError(null);

    try {
      const result = await saveJob(jobId);
      onApplicationChange(jobId, result);
    } catch {
      setError("Could not save job.");
    } finally {
      setPending(null);
    }
  }

  // Records that the user applied (on the employer's site) - it never
  // submits anything. An untracked job is saved first, since tracking is
  // one (user, job) record that moves from saved to applied (AJI-023).
  async function handleMarkApplied() {
    setPending("apply");
    setError(null);

    let tracked = application;

    try {
      if (!tracked) {
        tracked = await saveJob(jobId);
        onApplicationChange(jobId, tracked);
      }

      const result = await updateApplicationStatus(tracked.id, "applied");
      onApplicationChange(jobId, result);
    } catch {
      setError(
        tracked
          ? "Saved, but could not mark as applied. Try again."
          : "Could not mark as applied.",
      );
    } finally {
      setPending(null);
    }
  }

  async function handleRemove() {
    if (!application) return;

    setPending("remove");
    setError(null);

    try {
      await removeSavedJob(application.id);
      onApplicationChange(jobId, null);
    } catch {
      setError("Could not remove saved job.");
    } finally {
      setPending(null);
    }
  }

  if (!application) {
    return (
      <div className="flex flex-col items-end gap-2">
        <AppButton
          variant="secondary"
          loading={pending === "save"}
          disabled={pending === "apply"}
          onClick={handleSave}
          aria-label="Save job"
        >
          <Bookmark className="h-3.5 w-3.5" aria-hidden="true" />
          Save
        </AppButton>
        <AppButton
          variant="ghost"
          size="sm"
          loading={pending === "apply"}
          disabled={pending === "save"}
          onClick={handleMarkApplied}
        >
          Mark as Applied
        </AppButton>
        {error && <p className="text-xs text-app-danger-text">{error}</p>}
      </div>
    );
  }

  // Once the user has explicitly marked the job Applied (or further
  // along), it's an Application, not merely a saved job - NERO never
  // auto-applies, so this state only ever comes from the user's own
  // "Mark as Applied" action or a status update on the Application
  // Detail page, never from clicking the external Apply link.
  if (application.status !== "saved") {
    return (
      <div className="flex flex-col items-end gap-2">
        <Badge tone="blue-soft">
          {formatApplicationStatus(application.status)}
        </Badge>
        <AppButton
          variant="ghost"
          size="sm"
          href={`/applications/${application.id}`}
        >
          View Application
        </AppButton>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <AppButton
        variant="secondary"
        disabled
        aria-label="Job saved"
      >
        <BookmarkCheck className="h-3.5 w-3.5" aria-hidden="true" />
        Saved
      </AppButton>
      <AppButton
        variant="primary"
        size="sm"
        loading={pending === "apply"}
        onClick={handleMarkApplied}
      >
        Mark as Applied
      </AppButton>
      <AppButton
        variant="ghost"
        size="sm"
        href={`/applications/${application.id}`}
      >
        View in Tracking
      </AppButton>
      <AppButton
        variant="ghost"
        size="sm"
        loading={pending === "remove"}
        onClick={handleRemove}
      >
        Remove
      </AppButton>
      {error && <p className="text-xs text-app-danger-text">{error}</p>}
    </div>
  );
}

function JobCard({
  job,
  application,
  onApplicationChange,
  onOpen,
  hideTracking = false,
  intelligenceStatus,
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
  gapAnalysis,
  isCalculatingGapAnalysis,
  gapAnalysisError,
  onCalculateGapAnalysis,
  improvement,
  isSubmittingImprovement,
  isRecheckingImprovement,
  improvementError,
  onApproveImprovements,
  onRunRecheck,
}: {
  job: Job;
  application?: Application;
  onApplicationChange: (jobId: string, application: Application | null) => void;
  /** Opens this job's full workflow view (AJI-023); absent there. */
  onOpen?: (jobId: string) => void;
  /** The workflow view hosts the tracking controls in its own panel. */
  hideTracking?: boolean;
  intelligenceStatus?: string;
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
  gapAnalysis?: GapAnalysisResult;
  isCalculatingGapAnalysis: boolean;
  gapAnalysisError?: string;
  onCalculateGapAnalysis: (jobId: string) => void;
  improvement?: ResumeImprovementResult;
  isSubmittingImprovement: boolean;
  isRecheckingImprovement: boolean;
  improvementError?: string;
  onApproveImprovements: (
    jobId: string,
    gapAnalysisId: string,
    decisions: ImprovementDecisionInput[],
  ) => void;
  onRunRecheck: (jobId: string, improvementId: string) => void;
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
              {job.is_test_data && <Badge tone="danger">Test data</Badge>}
              {job.employment_type && (
                <Badge tone={employmentTypeTone(job.employment_type)}>
                  {formatEmploymentType(job)}
                </Badge>
              )}
              {job.location && <Badge>{job.location}</Badge>}
              {job.remote_type && <Badge>{formatValue(job.remote_type)}</Badge>}
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
                {formatJobOrigin(job)}
              </span>
            </div>
          </div>

          {/* ACTIONS */}
          <div className="flex shrink-0 flex-wrap gap-3 lg:flex-col lg:items-end">
            {onOpen && (
              <AppButton
                variant="primary"
                onClick={() => onOpen(job.id)}
                aria-label={`Open job workflow for ${job.title}`}
              >
                Open job
              </AppButton>
            )}

            {!hideTracking && (
              <JobTrackingActions
                jobId={job.id}
                application={application}
                onApplicationChange={onApplicationChange}
              />
            )}

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
          {/* JOB INTELLIGENCE (AJI-012) — first: every later stage reads it */}
          <div className="mb-4 rounded-lg border border-app-border bg-app-bg p-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-app-blue">
                  Job Intelligence
                </div>
                <p className="mt-1 text-xs leading-5 text-app-faint">
                  Structured, evidence-backed requirements extracted from
                  this JD. Not a score or a match — see Job Match below
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
              <JobIntelligencePanel
                intelligence={intelligence}
                extractionStatus={intelligenceStatus}
              />
            )}
          </div>

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

              <p className="mt-2 text-xs leading-5 text-app-faint">
                How well this job fits you overall — required/preferred
                skills and experience, role alignment, location, and
                employment type. Not the same as ATS Alignment (resume
                ↔ this JD only) and does not include Hard Eligibility.
              </p>

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

          {/* JOB MATCH DETAILS - kept with the Job Match score, apart from
              ATS Alignment's own requirement breakdown below. */}
          {match && (
            <div className="mt-4 font-mono text-[9px] uppercase tracking-[0.18em] text-app-faint">
              Job Match details
            </div>
          )}
          {match && (
            <div className="mt-2 grid gap-4 lg:grid-cols-3">
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

          {/* ATS ALIGNMENT DETAILS */}
          {ats && <AtsAlignmentPanel result={ats} />}

          {/* GAP ANALYSIS & JOB-SPECIFIC SUGGESTIONS (AJI-015) */}
          <GapAnalysisSection
            jobId={job.id}
            result={gapAnalysis}
            isLoading={isCalculatingGapAnalysis}
            error={gapAnalysisError}
            onCalculate={onCalculateGapAnalysis}
          />

          {/* RESUME IMPROVEMENT APPROVAL & RECHECK (AJI-021) */}
          <ResumeImprovementSection
            jobId={job.id}
            gapAnalysis={gapAnalysis}
            result={improvement}
            isSubmitting={isSubmittingImprovement}
            isRechecking={isRecheckingImprovement}
            error={improvementError}
            onApprove={onApproveImprovements}
            onRunRecheck={onRunRecheck}
          />

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
  extractionStatus,
}: {
  intelligence: JobIntelligenceData;
  extractionStatus?: string;
}) {
  const { location, identity, domain, compensation } = intelligence;
  const place = [location.city, location.state, location.country]
    .filter(Boolean)
    .join(", ");
  const hasCompensation =
    compensation.salary_min !== null || compensation.salary_max !== null;

  return (
    <div className="mt-4">
      {/* AJI-023: say plainly when only the deterministic stage ran (no AI
          provider result) - never present it as AI-verified. */}
      {extractionStatus === "partial" && (
        <p className="mb-3 rounded-md border border-app-border px-3 py-2 text-[11px] leading-5 text-app-faint">
          Deterministic extraction only — AI enrichment was not available
          for this analysis. Every item below is quoted from the job
          description.
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="min-w-0 rounded-lg border border-app-border p-3">
          <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
            Identity
          </div>
          <dl className="mt-2 space-y-1 break-words text-xs text-app-text">
            <IntelligenceField
              label="Normalized title"
              value={identity.normalized_title ?? "Unknown"}
            />
            <IntelligenceField
              label="Role family"
              value={identity.role_family ?? "Unknown"}
            />
            <IntelligenceField
              label="Seniority"
              value={identity.seniority ?? "Unknown"}
            />
            <IntelligenceField
              label="Employment type"
              value={formatValue(intelligence.employment.employment_type)}
            />
            <IntelligenceField
              label="Domain"
              value={
                domain.value
                  ? `${domain.value}${
                      domain.confidence
                        ? ` (${domain.confidence} confidence)`
                        : ""
                    }`
                  : "Unknown"
              }
            />
            {hasCompensation && (
              <IntelligenceField
                label="Compensation"
                value={`${compensation.currency ?? ""} ${
                  compensation.salary_min?.toLocaleString() ?? "?"
                } – ${compensation.salary_max?.toLocaleString() ?? "?"}${
                  compensation.period !== "unknown"
                    ? ` / ${formatValue(compensation.period)}`
                    : ""
                }`.trim()}
              />
            )}
          </dl>
        </div>

        <div className="min-w-0 rounded-lg border border-app-border p-3">
          <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
            Location &amp; Authorization
          </div>
          <dl className="mt-2 space-y-1 break-words text-xs text-app-text">
            {place && <IntelligenceField label="Location" value={place} />}
            <IntelligenceField
              label="Arrangement"
              value={formatValue(location.remote_type)}
            />
            {location.work_arrangement_text && (
              <IntelligenceField
                label="Evidence"
                value={location.work_arrangement_text}
              />
            )}
            <IntelligenceField
              label="Work authorization"
              value={formatValue(intelligence.authorization.work_authorization)}
            />
            <IntelligenceField
              label="Sponsorship"
              value={formatValue(intelligence.authorization.sponsorship)}
            />
            <IntelligenceField
              label="Citizenship"
              value={formatValue(intelligence.authorization.citizenship)}
            />
            <IntelligenceField
              label="Clearance"
              value={formatValue(intelligence.authorization.clearance)}
            />
          </dl>
        </div>

        <RequirementList
          title="Required Skills"
          items={intelligence.required_skills.map((item) => ({
            label: item.canonical_skill,
            detail: item.evidence_text,
            confidence: item.confidence,
          }))}
          emptyLabel="No explicit required skills detected."
        />

        <RequirementList
          title="Preferred Skills"
          items={intelligence.preferred_skills.map((item) => ({
            label: item.canonical_skill,
            detail: item.evidence_text,
            confidence: item.confidence,
          }))}
          emptyLabel="No explicit preferred skills detected."
        />

        <RequirementList
          title="Experience"
          items={[
            ...intelligence.required_experience,
            ...intelligence.preferred_experience,
          ].map((item) => ({
            label: `${formatYears(item.minimum_years, item.maximum_years)}${
              item.area ? ` — ${item.area}` : ""
            }`,
            detail: item.evidence_text,
            confidence: item.confidence,
            level: item.level,
          }))}
          emptyLabel="No explicit years-of-experience requirements detected."
        />

        <RequirementList
          title="Education & Certifications"
          items={[
            ...intelligence.education.map((item) => ({
              label:
                [item.degree_level, item.field_of_study]
                  .filter(Boolean)
                  .map((part) => formatValue(part as string))
                  .join(" — ") || "Education requirement",
              detail: item.evidence_text,
              confidence: item.confidence,
              level: item.level,
            })),
            ...intelligence.certifications.map((item) => ({
              label: item.name,
              detail: item.evidence_text,
              confidence: item.confidence,
              level: item.level,
            })),
          ]}
          emptyLabel="No education or certification requirements detected."
        />

        <div className="lg:col-span-2">
          <RequirementList
            title="Responsibilities"
            items={intelligence.responsibilities.map((item) => ({
              label: item.description,
            }))}
            emptyLabel="No responsibilities detected."
          />
        </div>
      </div>
    </div>
  );
}

function IntelligenceField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="inline text-app-faint">{label}: </dt>
      <dd className="inline">{value}</dd>
    </div>
  );
}

function formatYears(min: number | null, max: number | null): string {
  if (min !== null && max !== null && max !== min) return `${min}–${max} years`;
  if (min !== null) return `${min}+ years`;
  if (max !== null) return `Up to ${max} years`;
  return "Experience";
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

      {result.score_components.length > 0 && (
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {result.score_components.map((component) => (
            <div
              key={component.name}
              className="rounded-md border border-app-border px-2 py-1.5"
              title={component.explanation}
            >
              <div className="font-mono text-[8px] uppercase tracking-[0.1em] text-app-faint">
                {atsComponentLabel(component.name)}
              </div>
              <div className="mt-0.5 text-sm font-semibold text-app-text">
                {Math.round(component.score)}%
              </div>
            </div>
          ))}
        </div>
      )}

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

const ATS_COMPONENT_LABELS: Record<string, string> = {
  requirement_coverage: "Coverage",
  keyword_terminology_alignment: "Keywords",
  resume_evidence_experience: "Evidence",
  structure_parseability: "Structure",
};

function atsComponentLabel(name: string): string {
  return ATS_COMPONENT_LABELS[name] ?? name;
}

function RequirementList({
  title,
  items,
  emptyLabel,
}: {
  title: string;
  items: Array<{
    label: string;
    detail?: string;
    confidence?: string;
    level?: "required" | "preferred";
  }>;
  emptyLabel: string;
}) {
  const visible = items.slice(0, 8);

  return (
    <div className="min-w-0 rounded-lg border border-app-border p-3">
      <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
        {title}
      </div>

      {items.length === 0 ? (
        <p className="mt-2 text-xs text-app-faint">{emptyLabel}</p>
      ) : (
        <ul className="mt-2 space-y-2">
          {visible.map((item, index) => (
            <li key={`${item.label}-${index}`} className="break-words text-xs">
              <div className="font-medium text-app-text">{item.label}</div>
              {item.detail && (
                <div className="mt-0.5 text-app-faint">{item.detail}</div>
              )}
              {(item.level || item.confidence) && (
                <div className="mt-0.5 font-mono text-[8px] uppercase tracking-[0.1em] text-app-faint">
                  {[item.level, item.confidence && `${item.confidence} confidence`]
                    .filter(Boolean)
                    .join(" · ")}
                </div>
              )}
            </li>
          ))}
          {items.length > visible.length && (
            <li className="text-[11px] text-app-faint">
              +{items.length - visible.length} more
            </li>
          )}
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
