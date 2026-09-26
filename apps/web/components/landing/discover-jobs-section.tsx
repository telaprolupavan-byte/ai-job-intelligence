"use client";

import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState, useTransition } from "react";
import Image from "next/image";
import Link from "next/link";
import { Dialog } from "@base-ui/react/dialog";
import {
  Search as SearchIcon,
  MapPin,
  SlidersHorizontal,
  Lock,
  ArrowRight,
  X,
} from "lucide-react";
import { getJobs, type Job } from "@/lib/jobs";
import Badge from "@/components/app/badge";
import AppButton from "@/components/app/app-button";
import { Skeleton } from "@/components/app/skeleton";
import SectionHeading from "@/components/landing/section-heading";
import { cn } from "@/lib/utils";

type EmploymentFilter = "" | "full_time" | "contract" | "internship";
type RemoteFilter = "" | "remote" | "hybrid" | "onsite";

type DiscoverFilters = {
  search: string;
  employmentType: EmploymentFilter;
  remoteType: RemoteFilter;
  location: string;
};

const EMPTY_FILTERS: DiscoverFilters = {
  search: "",
  employmentType: "",
  remoteType: "",
  location: "",
};

// Kept deliberately small — this is a curated product demo on the
// marketing page, not the full paginated Jobs workspace (that lives at
// /jobs behind sign-in). Three cards is enough to show what NERO surfaces
// without the section reading like a job board.
const PAGE_SIZE = 3;

// Excluded from this landing-page preview only — the real /jobs API,
// the Jobs page, and the underlying job-discovery data are untouched.
// Matched by exact title against whatever the live search returns.
const LANDING_PREVIEW_EXCLUDED_TITLES = new Set([
  "Boston ML Engineer",
  "Remote AI Engineer",
  "Contract ML Engineer",
]);

const EMPLOYMENT_OPTIONS: { value: EmploymentFilter; label: string }[] = [
  { value: "full_time", label: "Full-Time" },
  { value: "contract", label: "Contract" },
  { value: "internship", label: "Internship" },
];

const REMOTE_OPTIONS: { value: RemoteFilter; label: string }[] = [
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-Site" },
];

const BLUE_BUTTON_CLASS =
  "app-focus-ring inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-app-blue px-5 text-xs font-bold uppercase tracking-[0.1em] text-black transition hover:bg-app-blue-hover";

export default function DiscoverJobsSection() {
  const [draft, setDraft] = useState({ search: "", location: "" });
  const [applied, setApplied] = useState<DiscoverFilters>(EMPTY_FILTERS);

  const [jobs, setJobs] = useState<Job[]>([]);
  const [totalJobs, setTotalJobs] = useState<number | null>(null);
  const [isPending, startTransition] = useTransition();
  const [hasLoaded, setHasLoaded] = useState(false);
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  // This section sits well below the fold. Firing its request during
  // hydration put a job-board fetch in direct competition with the
  // hero's own assets for connections and main-thread time, for a
  // section a visitor may never scroll to. The shell renders
  // immediately either way — only the data is deferred, and only until
  // the section is within a viewport of being seen.
  const sectionRef = useRef<HTMLElement | null>(null);
  const [isNearViewport, setIsNearViewport] = useState(false);

  useEffect(() => {
    const node = sectionRef.current;
    if (!node) return;

    // IntersectionObserver is already a hard dependency of the page's
    // reveal/parallax layer, so no capability fallback is needed here.
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setIsNearViewport(true);
          observer.disconnect();
        }
      },
      { rootMargin: "100% 0px" },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const runSearch = useCallback((filters: DiscoverFilters) => {
    startTransition(async () => {
      try {
        const response = await getJobs({
          search: filters.search || undefined,
          employment_type: filters.employmentType || undefined,
          remote_type: filters.remoteType || undefined,
          location: filters.location || undefined,
          page: 1,
          page_size: PAGE_SIZE,
        });

        setJobs(
          response.jobs.filter(
            (job) => !LANDING_PREVIEW_EXCLUDED_TITLES.has(job.title),
          ),
        );
        setTotalJobs(response.pagination.total);
      } catch (err) {
        // The landing page must never depend on this request. A failure
        // leaves the panel in its "connect your resume" state, which is
        // a valid thing for a signed-out visitor to see.
        console.error(err);
      } finally {
        setHasLoaded(true);
      }
    });
  }, [startTransition]);

  useEffect(() => {
    if (!isNearViewport) return;
    runSearch(applied);
  }, [applied, runSearch, isNearViewport]);

  function handleSearchSubmit(event: React.FormEvent) {
    event.preventDefault();
    setApplied((current) => ({
      ...current,
      search: draft.search.trim(),
      location: draft.location.trim(),
    }));
    setMobileFiltersOpen(false);
  }

  function toggleEmployment(value: EmploymentFilter) {
    setApplied((current) => ({
      ...current,
      employmentType: current.employmentType === value ? "" : value,
    }));
  }

  function toggleRemote(value: RemoteFilter) {
    setApplied((current) => ({
      ...current,
      remoteType: current.remoteType === value ? "" : value,
    }));
  }

  function clearAll() {
    setDraft({ search: "", location: "" });
    setApplied(EMPTY_FILTERS);
    setMobileFiltersOpen(false);
  }

  function applyDraft() {
    setApplied((current) => ({
      ...current,
      search: draft.search.trim(),
      location: draft.location.trim(),
    }));
  }

  const activeFilterCount = [
    applied.search,
    applied.employmentType,
    applied.remoteType,
    applied.location,
  ].filter(Boolean).length;

  // Illustrative-only: how many of the loaded results score >= 85 on the
  // sample match scale below. Real Job Match requires a signed-in
  // resume, so this is clearly labeled everywhere it's shown.
  const sampleStrongMatches = jobs.filter(
    (_, index) => sampleMatchScore(index) >= 85,
  ).length;

  // Real: how many of the loaded results were posted/first seen today.
  const newTodayCount = jobs.filter((job) => {
    const timestamp = job.posting_date ?? job.first_seen_at;
    return timestamp && formatRelativeTime(timestamp) === "Today";
  }).length;

  return (
    <section
      ref={sectionRef}
      id="how-it-works"
      className="relative overflow-hidden border-t border-white/10 bg-app-bg"
    >
      <div
        className="technical-grid absolute inset-0 opacity-30"
        aria-hidden="true"
      />
      <div
        data-parallax-speed="0.07"
        data-parallax-local
        className="nero-atmosphere absolute inset-0"
        aria-hidden="true"
      />

      <div className="landing-shell landing-band">
        <div className="discover-hero-grid">
          {/* HEADLINE — mobile order: 1st */}
          <div className="discover-hero-area-content">
            <SectionHeading
              eyebrow="DISCOVER JOBS"
              title={
                <>
                  REAL JOBS.
                  <br />
                  <span className="bg-gradient-to-r from-[#8fdcff] via-[#5cc6ff] to-app-blue bg-clip-text text-transparent">
                    REAL OPPORTUNITIES.
                  </span>
                </>
              }
              lede="Search U.S. opportunities with intelligent filters and discover roles that align with your experience, skills, and preferences."
            />
          </div>

          {/* MASCOT — mobile order: 2nd. MEDIUM motion tier: NERO gets
              restrained local depth; the search card and job data below
              stay motion-free so they remain readable and usable while
              scrolling.

              Character pass: this is the SEARCHING beat, and it now uses
              the approved Page 2 Explainer export instead of the generic
              Page 1 standing pose. That artwork already has NERO holding
              a live JOBS panel — Full-Time / Contract / Remote / Hybrid,
              a search glyph and a U.S. coverage map — which is precisely
              the filter set and national scope this section is about, so
              he reads as running the search rather than standing next to
              a search form. Idle float is quicker and shallower than the
              default (5.2s / 15px): scanning, not drifting. */}
          <div className="discover-hero-area-nero relative flex justify-center lg:justify-end">
            <div className="relative w-full max-w-[360px]">
              <div
                data-parallax-speed="0.09"
                data-parallax-local
                className="pointer-events-none absolute -bottom-12 left-1 z-20 hidden -rotate-2 text-left xl:block"
                aria-hidden="true"
              >
                <p className="nero-note text-app-blue">
                  Smarter
                  <br />
                  Searches.
                  <br />
                  Brighter Careers!
                </p>
              </div>

              <div className="pointer-events-none absolute right-0 top-0 z-20 max-w-[210px]">
                <div className="rounded-xl border border-app-border-soft bg-app-panel/85 px-4 py-3 text-left shadow-lg backdrop-blur-sm">
                  <p className="text-xs leading-5 text-app-body">
                    I&apos;ll help you find the best opportunities based on
                    your skills, goals, and preferences.
                  </p>
                </div>
              </div>

              <div
                data-parallax-speed="0.09"
                data-parallax-scale-to="1.04"
                data-parallax-local
                className="relative w-full px-10 pt-16 sm:px-12 lg:px-4 lg:pt-12"
              >
                <Image
                  src="/brand/nero-page2-explainer.png"
                  alt="NERO, the AI Job Intelligence mascot, running a job search on a panel of Full-Time, Contract, Remote and Hybrid filters across the U.S."
                  width={780}
                  height={936}
                  sizes="(min-width: 1024px) 340px, (min-width: 640px) 300px, 260px"
                  quality={95}
                  style={
                    {
                      "--nero-float-duration": "5.2s",
                      "--nero-float-distance": "15px",
                    } as CSSProperties
                  }
                  className="nero-float relative z-10 h-auto w-full drop-shadow-[0_30px_60px_rgba(0,0,0,0.55)]"
                />

                <div
                  className="nero-floor-glow pointer-events-none absolute -bottom-2 left-1/2 h-20 w-[70%] -translate-x-1/2"
                  aria-hidden="true"
                />
              </div>
            </div>
          </div>

          {/* SEARCH — mobile order: 3rd */}
          <div className="discover-hero-area-search">
            <form
              onSubmit={handleSearchSubmit}
              className="glass-panel rounded-2xl border border-app-border-soft p-4 sm:p-5"
            >
              <div className="flex flex-col gap-3 sm:flex-row">
                <label htmlFor="discover-search" className="sr-only">
                  Search job title, skill, company, or keyword
                </label>
                <div className="relative flex-1">
                  <SearchIcon
                    className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-app-faint"
                    aria-hidden="true"
                  />
                  <input
                    id="discover-search"
                    type="text"
                    value={draft.search}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        search: event.target.value,
                      }))
                    }
                    placeholder="Search job title, skill, company, or keyword"
                    className="app-focus-ring w-full rounded-lg border border-app-border bg-app-surface py-3.5 pl-11 pr-4 text-sm text-app-text placeholder:text-app-faint focus:border-app-blue"
                  />
                </div>

                <div className="relative sm:w-56">
                  <label htmlFor="discover-location" className="sr-only">
                    City or state
                  </label>
                  <MapPin
                    className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-app-faint"
                    aria-hidden="true"
                  />
                  <input
                    id="discover-location"
                    type="text"
                    value={draft.location}
                    onChange={(event) =>
                      setDraft((current) => ({
                        ...current,
                        location: event.target.value,
                      }))
                    }
                    placeholder="City or state"
                    className="app-focus-ring w-full rounded-lg border border-app-border bg-app-surface py-3.5 pl-11 pr-4 text-sm text-app-text placeholder:text-app-faint focus:border-app-blue"
                  />
                </div>

                <AppButton type="submit" className="sm:w-auto">
                  <SearchIcon className="h-3.5 w-3.5" aria-hidden="true" />
                  Search
                </AppButton>
              </div>

              {/* QUICK FILTERS */}
              <div className="mt-4 flex flex-wrap items-center gap-2">
                {EMPLOYMENT_OPTIONS.map((option) => (
                  <FilterChip
                    key={option.value}
                    label={option.label}
                    active={applied.employmentType === option.value}
                    onClick={() => toggleEmployment(option.value)}
                  />
                ))}

                {REMOTE_OPTIONS.map((option) => (
                  <FilterChip
                    key={option.value}
                    label={option.label}
                    active={applied.remoteType === option.value}
                    onClick={() => toggleRemote(option.value)}
                  />
                ))}

                <span
                  className="inline-flex cursor-default items-center gap-1.5 rounded-full border border-app-border/60 bg-app-surface/60 px-4 py-2 text-xs font-medium uppercase tracking-wider text-app-faint"
                  title="NERO currently sources U.S. opportunities only."
                >
                  <Lock className="h-3 w-3" aria-hidden="true" />
                  US Only
                </span>

                {activeFilterCount > 0 && (
                  <button
                    type="button"
                    onClick={clearAll}
                    className="app-focus-ring ml-1 inline-flex items-center gap-1 rounded-full px-2 py-2 text-xs font-medium text-app-faint transition hover:text-app-text"
                  >
                    <X className="h-3 w-3" aria-hidden="true" />
                    Clear
                  </button>
                )}
              </div>
            </form>

            {/* STAT STRIP — moved inside the search column so the
                section reads as one instrument (copy | NERO over
                search + stats) instead of four stacked blocks each at
                a different width. */}
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile
                value={
                  totalJobs === null
                    ? "—"
                    : `${totalJobs.toLocaleString()}${totalJobs > 0 ? "+" : ""}`
                }
                label="Matching opportunities"
              />
              <StatTile
                value={jobs.length === 0 ? "—" : String(sampleStrongMatches)}
                label="Strong matches"
                hint="Example — sign in to calculate"
              />
              <StatTile
                value={jobs.length === 0 ? "—" : String(newTodayCount)}
                label="New today"
                hint="In results shown"
              />
              <StatTile value="Live" label="Job updates" />
            </div>

            {/* MOBILE FILTERS TRIGGER */}
            <div className="mt-4 lg:hidden">
              <Dialog.Root
                open={mobileFiltersOpen}
                onOpenChange={setMobileFiltersOpen}
              >
                <Dialog.Trigger className="app-focus-ring inline-flex w-full items-center justify-center gap-2 rounded-lg border border-app-border-strong bg-app-panel px-4 py-3 text-xs font-bold uppercase tracking-[0.1em] text-app-text transition hover:border-app-blue">
                  <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
                  Filters
                  {activeFilterCount > 0 && (
                    <Badge tone="blue-soft">{activeFilterCount}</Badge>
                  )}
                </Dialog.Trigger>

                <Dialog.Portal>
                  <Dialog.Backdrop className="fixed inset-0 z-40 bg-black/60 transition-opacity duration-200 data-[starting-style]:opacity-0 data-[ending-style]:opacity-0" />

                  <Dialog.Popup
                    aria-label="Job filters"
                    className="fixed inset-x-0 bottom-0 z-50 max-h-[85vh] overflow-y-auto rounded-t-2xl border-t border-app-border bg-app-bg p-5 outline-none transition-transform duration-200 data-[starting-style]:translate-y-full data-[ending-style]:translate-y-full"
                  >
                    <div className="mb-4 flex items-center justify-between">
                      <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-app-blue">
                        Filters
                      </span>
                      <Dialog.Close
                        className="app-focus-ring flex h-8 w-8 items-center justify-center rounded-lg text-app-muted hover:text-app-text"
                        aria-label="Close filters"
                      >
                        <X className="h-4 w-4" aria-hidden="true" />
                      </Dialog.Close>
                    </div>

                    <FilterPanelBody
                      applied={applied}
                      toggleEmployment={toggleEmployment}
                      toggleRemote={toggleRemote}
                    />

                    <div className="mt-6 flex gap-3">
                      <AppButton
                        type="button"
                        variant="ghost"
                        className="flex-1"
                        onClick={clearAll}
                      >
                        Clear All
                      </AppButton>
                      <button
                        type="button"
                        className={cn(BLUE_BUTTON_CLASS, "flex-1")}
                        onClick={() => {
                          applyDraft();
                          setMobileFiltersOpen(false);
                        }}
                      >
                        Apply Filters
                      </button>
                    </div>
                  </Dialog.Popup>
                </Dialog.Portal>
              </Dialog.Root>
            </div>
          </div>
        </div>

        {/* MAIN DISCOVERY AREA — framed as one console-like instrument
            rather than a raw two-column grid loose inside the section's
            full canvas, so it reads as a composed scene instead of a
            dashboard widget dropped onto the page. */}
        <div className="stack-xl relative mx-auto max-w-[1060px] overflow-hidden rounded-3xl border border-white/10 bg-app-panel/30 p-5 sm:p-6">
          <div
            data-parallax-speed="0.05"
            data-parallax-scale-to="1.03"
            data-parallax-local
            className="technical-grid absolute inset-0 opacity-20"
            aria-hidden="true"
          />

          <div id="discover-results" className="discover-grid relative">
            {/* FILTER PANEL (desktop) */}
            <aside
              data-reveal
              style={{ "--reveal-distance": "12px" } as CSSProperties}
              className="discover-area-filters hidden lg:block"
            >
              <div className="rounded-2xl border border-app-border bg-app-panel/70 p-5">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-app-blue">
                    Filters
                  </span>
                  {activeFilterCount > 0 && (
                    <button
                      type="button"
                      onClick={clearAll}
                      className="app-focus-ring text-[10px] font-semibold uppercase tracking-[0.1em] text-app-faint hover:text-app-text"
                    >
                      Clear All
                    </button>
                  )}
                </div>

                {/* Two inner columns on the desktop console only. In
                    one column the six filter groups made this panel
                    ~860px tall against a ~540px insights column, so
                    the console's own border enclosed 300px of nothing.
                    Same filters, same order, half the height. */}
                <div className="mt-4">
                  <FilterPanelBody
                    applied={applied}
                    toggleEmployment={toggleEmployment}
                    toggleRemote={toggleRemote}
                    columns
                  />
                </div>

                <button
                  type="button"
                  className={cn(BLUE_BUTTON_CLASS, "mt-5")}
                  onClick={applyDraft}
                >
                  Apply Filters
                </button>
              </div>
            </aside>

            {/* NERO INSIGHTS */}
            <div
              data-reveal
              data-reveal-delay="100"
              style={{ "--reveal-distance": "12px" } as CSSProperties}
              className="discover-area-insights flex flex-col gap-4"
            >
              <NeroInsightsPanel
                jobs={jobs}
                loading={!hasLoaded || (isPending && jobs.length === 0)}
              />
              <WhyNeroFoundThese filters={applied} />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "app-focus-ring inline-flex items-center rounded-full border px-4 py-2 text-xs font-medium uppercase tracking-wider transition",
        active
          ? "border-transparent bg-app-blue-soft text-app-blue"
          : "border-app-border bg-app-surface text-app-body hover:border-app-border-strong hover:text-app-text",
      )}
    >
      {label}
    </button>
  );
}

function StatTile({
  value,
  label,
  hint,
}: {
  value: string;
  label: string;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-app-border bg-app-panel/70 px-4 py-3.5">
      <div className="text-xl font-bold text-app-text sm:text-2xl">
        {value}
      </div>
      <div className="mt-1 text-[11px] leading-4 text-app-muted">{label}</div>
      {hint && (
        <div className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.1em] text-app-faint">
          {hint}
        </div>
      )}
    </div>
  );
}

function FilterPanelBody({
  applied,
  toggleEmployment,
  toggleRemote,
  columns,
}: {
  applied: DiscoverFilters;
  toggleEmployment: (value: EmploymentFilter) => void;
  toggleRemote: (value: RemoteFilter) => void;
  columns?: boolean;
}) {
  return (
    <div
      className={cn(
        "space-y-6",
        columns && "sm:grid sm:grid-cols-2 sm:gap-x-6 sm:gap-y-6 sm:space-y-0",
      )}
    >
      <FilterGroup title="Job Type">
        <div className="space-y-2">
          {EMPLOYMENT_OPTIONS.map((option) => (
            <CheckboxRow
              key={option.value}
              label={option.label}
              checked={applied.employmentType === option.value}
              onChange={() => toggleEmployment(option.value)}
            />
          ))}
        </div>
      </FilterGroup>

      <FilterGroup title="Work Model">
        <div className="space-y-2">
          {REMOTE_OPTIONS.map((option) => (
            <CheckboxRow
              key={option.value}
              label={option.label}
              checked={applied.remoteType === option.value}
              onChange={() => toggleRemote(option.value)}
            />
          ))}
        </div>
      </FilterGroup>

      <FilterGroup title="Location">
        <div className="space-y-2">
          <div className="flex items-center justify-between rounded-lg border border-app-border bg-app-surface px-3 py-2 text-xs text-app-body">
            United States
            <Lock
              className="h-3 w-3 text-app-faint"
              aria-hidden="true"
            />
          </div>
          <p className="text-[11px] leading-4 text-app-faint">
            More countries coming soon — enter a city or state in the search
            bar above to narrow results.
          </p>
        </div>
      </FilterGroup>

      <FilterGroup title="Experience Level" locked>
        <div className="space-y-2 opacity-50">
          {["Entry", "Mid", "Senior"].map((label) => (
            <CheckboxRow key={label} label={label} checked={false} disabled />
          ))}
        </div>
      </FilterGroup>

      <FilterGroup title="Salary Range" locked>
        <div className="opacity-50">
          <div className="h-1.5 w-full rounded-full bg-app-border" />
          <div className="mt-2 flex justify-between font-mono text-[9px] text-app-faint">
            <span>$0</span>
            <span>$300K+</span>
          </div>
        </div>
      </FilterGroup>

      <FilterGroup title="Skills" locked>
        <div className="flex flex-wrap gap-1.5 opacity-50">
          {["Python", "AWS", "LLM", "Data Analysis"].map((skill) => (
            <span
              key={skill}
              className="rounded-full border border-app-border px-2.5 py-1 text-[10px] text-app-faint"
            >
              {skill}
            </span>
          ))}
        </div>
      </FilterGroup>

      <button
        type="button"
        disabled
        className="flex items-center gap-1.5 text-xs font-medium text-app-faint opacity-60"
      >
        <Lock className="h-3 w-3" aria-hidden="true" />+ Add more filters
      </button>
    </div>
  );
}

function FilterGroup({
  title,
  locked,
  children,
}: {
  title: string;
  locked?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-muted">
          {title}
        </span>
        {locked && (
          <span className="inline-flex items-center gap-1 rounded-full border border-app-border/60 px-2 py-0.5 font-mono text-[8px] uppercase tracking-[0.1em] text-app-faint">
            <Lock className="h-2.5 w-2.5" aria-hidden="true" />
            Coming soon
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

function CheckboxRow({
  label,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  checked: boolean;
  onChange?: () => void;
  disabled?: boolean;
}) {
  return (
    <label
      className={cn(
        "flex items-center gap-2.5 text-sm",
        disabled ? "cursor-not-allowed text-app-faint" : "cursor-pointer text-app-body",
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        readOnly={!onChange}
        className="app-focus-ring h-4 w-4 rounded border-app-border-strong bg-app-surface text-app-blue accent-app-blue"
      />
      {label}
    </label>
  );
}

function getInitials(company: string | null): string {
  if (!company) return "N";

  const words = company.trim().split(/\s+/).slice(0, 2);
  return words.map((word) => word[0]?.toUpperCase() ?? "").join("") || "N";
}

function formatLabel(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatSalary(job: Job): string {
  const currency = job.salary_currency || "USD";

  if (job.salary_min !== null && job.salary_max !== null) {
    return `${currency} ${Math.round(job.salary_min).toLocaleString()}–${Math.round(job.salary_max).toLocaleString()}`;
  }
  if (job.salary_min !== null) {
    return `From ${currency} ${Math.round(job.salary_min).toLocaleString()}`;
  }
  if (job.salary_max !== null) {
    return `Up to ${currency} ${Math.round(job.salary_max).toLocaleString()}`;
  }
  return "";
}

function formatRelativeTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";

  const diffMs = Date.now() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays <= 0) return "Today";
  if (diffDays === 1) return "1 day ago";
  if (diffDays < 30) return `${diffDays} days ago`;

  const diffMonths = Math.floor(diffDays / 30);
  return `${diffMonths} month${diffMonths > 1 ? "s" : ""} ago`;
}

// Illustrative-only descending scale (95, 91, 87, ...) so the sample
// cards read like a "best match first" list, exactly like the reference.
// Never presented without the "example" disclosure alongside it — the
// real Job Match score requires a signed-in user's resume.
function sampleMatchScore(index: number): number {
  return Math.max(65, 95 - index * 4);
}

function matchTone(score: number): "success" | "blue" | "amber" {
  if (score >= 85) return "success";
  if (score >= 70) return "blue";
  return "amber";
}

const MATCH_TONE_CLASS: Record<string, string> = {
  success: "bg-app-success text-black",
  blue: "bg-app-blue text-black",
  amber: "bg-app-amber text-black",
};

function MatchBadge({ score, small }: { score: number; small?: boolean }) {
  const tone = matchTone(score);

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full font-bold",
        small ? "px-2.5 py-0.5 text-[10px]" : "px-3 py-1 text-xs",
        MATCH_TONE_CLASS[tone],
      )}
      title="Example score — sign in and add your resume to calculate your real Job Match."
    >
      {score}% Match*
    </span>
  );
}

// Real, derived from the job's own fields — never fabricated. Only the
// numeric score above is illustrative; these lines describe the actual
// listing.
function deriveHighlights(job: Job): string[] {
  const highlights: string[] = [];

  if (job.remote_type) {
    highlights.push(
      job.remote_type === "remote"
        ? "Remote-friendly role"
        : job.remote_type === "hybrid"
          ? "Hybrid work model"
          : "On-site collaboration",
    );
  }

  const salary = formatSalary(job);
  if (salary) {
    highlights.push(`Compensation listed: ${salary}`);
  } else if (job.employment_type) {
    highlights.push(`${formatLabel(job.employment_type)} position`);
  }

  const timestamp = job.posting_date ?? job.first_seen_at;
  if (timestamp) {
    const relative = formatRelativeTime(timestamp);
    highlights.push(
      relative === "Today" || relative === "1 day ago"
        ? "Freshly posted"
        : "Actively hiring",
    );
  }

  return highlights.slice(0, 3);
}

function NeroInsightsPanel({
  jobs,
  loading,
}: {
  jobs: Job[];
  loading?: boolean;
}) {
  const topJobs = jobs.slice(0, 3);

  return (
    <div className="rounded-2xl border border-app-blue/40 bg-app-panel/70 p-4">
      <div className="flex items-center gap-2.5">
        <Image
          src="/brand/nero-mascot-logo.png"
          alt=""
          aria-hidden="true"
          width={1312}
          height={1199}
          // Without `sizes`, next/image assumes 100vw and serves a
          // 1920px-wide render — 258KB for a 28px-tall mark.
          sizes="32px"
          className="h-7 w-auto"
        />
        <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-app-blue">
          NERO Insights
        </span>
      </div>

      {loading ? (
        <div aria-hidden="true">
          <Skeleton className="mt-3 h-6 w-3/5" />
          <div className="mt-4 space-y-3">
            {[0, 1, 2].map((row) => (
              <div
                key={row}
                className="flex items-start gap-3 border-t border-app-border pt-3 first:border-t-0 first:pt-0"
              >
                <Skeleton className="h-9 w-9 shrink-0" />
                <div className="min-w-0 flex-1">
                  <Skeleton className="h-3.5 w-2/3" />
                  <Skeleton className="mt-2 h-3 w-2/5" />
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : topJobs.length > 0 ? (
        <>
          <h3 className="mt-3 text-lg font-semibold text-app-text">
            {topJobs.length} role{topJobs.length > 1 ? "s" : ""} stand out
            for you.*
          </h3>

          <div className="mt-4 space-y-3">
            {topJobs.map((job, index) => {
              const highlight = deriveHighlights(job)[0] ?? "Strong opportunity";

              return (
                <div
                  key={job.id}
                  className="flex items-start gap-3 border-t border-app-border pt-3 first:border-t-0 first:pt-0"
                >
                  <div
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-app-border-strong bg-app-surface text-xs font-bold text-app-blue"
                    aria-hidden="true"
                  >
                    {getInitials(job.company)}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-semibold text-app-text">
                        {job.title}
                      </span>
                      <MatchBadge score={sampleMatchScore(index)} small />
                    </div>
                    <p className="mt-0.5 text-xs leading-5 text-app-muted">
                      {highlight}.
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

          <p className="mt-4 text-[10px] leading-4 text-app-faint">
            * Illustrative example — sign in and add your resume to generate
            your real insights.
          </p>

          <a
            href="#discover-results"
            className="app-focus-ring mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-app-blue hover:text-app-blue-hover"
          >
            View All Insights
            <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </a>
        </>
      ) : (
        <>
          <h3 className="mt-3 text-lg font-semibold text-app-text">
            See why a job fits you.
          </h3>

          <p className="mt-2 text-sm leading-6 text-app-muted">
            Connect your resume and NERO explains exactly why a role
            matches — skills, experience, and requirements, side by side.
          </p>
        </>
      )}

      <Link
        href="/register"
        className="app-focus-ring mt-4 inline-flex items-center gap-2 rounded-lg bg-crimson-fill px-4 py-2.5 text-xs font-bold uppercase tracking-[0.08em] text-white transition hover:bg-crimson-fill-hover"
      >
        Create free account
        <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
      </Link>

      <Link
        href="/login"
        className="app-focus-ring mt-3 block text-center text-xs text-app-muted transition hover:text-app-text"
      >
        Already using NERO? Sign in
      </Link>
    </div>
  );
}

function WhyNeroFoundThese({ filters }: { filters: DiscoverFilters }) {
  const reasons: string[] = ["Sorted by the most recently posted"];

  if (filters.search) {
    reasons.push(`Matches your search for "${filters.search}"`);
  }
  if (filters.employmentType) {
    reasons.push(`Filtered to ${formatLabel(filters.employmentType)}`);
  }
  if (filters.remoteType) {
    reasons.push(`Filtered to ${formatLabel(filters.remoteType)}`);
  }
  if (filters.location) {
    reasons.push(`Near "${filters.location}"`);
  }

  reasons.push("Full Job Match & ATS Alignment unlock once you sign in");

  return (
    <div className="rounded-2xl border border-app-border bg-app-panel/70 p-4">
      <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-app-blue">
        Why NERO Found These
      </span>

      <ul className="mt-3 space-y-2.5">
        {reasons.map((reason) => (
          <li key={reason} className="flex items-start gap-2 text-xs leading-5 text-app-body">
            <span className="mt-0.5 text-app-blue" aria-hidden="true">
              ✓
            </span>
            {reason}
          </li>
        ))}
      </ul>
    </div>
  );
}
