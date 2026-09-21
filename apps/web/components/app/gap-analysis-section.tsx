"use client";

import type { GapAnalysisResult, GapSuggestion } from "@/lib/jobs";
import AppButton from "./app-button";
import Badge from "./badge";
import { Skeleton } from "./skeleton";

// AJI-015 — Gap Analysis & Job-Specific Suggestions (Figma node 116:15).
// Renders the existing GET/POST /jobs/{job_id}/gap-analysis result
// (apps/web/lib/jobs.ts getGapAnalysis/calculateGapAnalysis) against the
// Jobs page's single selected-resume-version source of truth. Never
// invents suggestion content — every field renders verbatim from the API
// response, with fallbacks only for missing/partial fields, not invented
// qualifications.

type GapAnalysisSectionProps = {
  jobId: string;
  result?: GapAnalysisResult;
  isLoading: boolean;
  error?: string;
  onCalculate: (jobId: string) => void;
};

export default function GapAnalysisSection({
  jobId,
  result,
  isLoading,
  error,
  onCalculate,
}: GapAnalysisSectionProps) {
  const gaps = result?.gaps ?? [];
  const gapCount = gaps.length;

  return (
    <div className="mt-4 rounded-lg border border-app-border bg-app-bg p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="font-mono text-[9px] uppercase tracking-[0.18em] text-app-blue">
            Gap Analysis
          </h3>
          <p className="mt-1 text-xs leading-5 text-app-faint">
            How this job differs from your selected resume
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          {!isLoading && !error && result && (
            <Badge tone={gapCount > 0 ? "blue-soft" : "success-soft"}>
              {gapCount} {gapCount === 1 ? "gap" : "gaps"}
            </Badge>
          )}

          <AppButton
            variant="ghost"
            size="sm"
            loading={isLoading}
            onClick={() => onCalculate(jobId)}
            aria-label={
              result ? "Recalculate Gap Analysis" : "Analyze job-specific gaps"
            }
          >
            {isLoading
              ? "Analyzing..."
              : result
                ? "Recalculate"
                : "Analyze Gaps"}
          </AppButton>
        </div>
      </div>

      <p className="mt-2 text-xs leading-5 text-app-faint">
        For each requirement your selected resume doesn&apos;t clearly
        demonstrate, NERO explains why it&apos;s a gap and what you could
        truthfully do about it. Not a score — see ATS Alignment above for
        that.
      </p>

      <div className="mt-3 rounded-md border border-app-border px-3 py-2">
        <p className="text-[11px] leading-5 text-app-faint">
          NERO only surfaces evidence-backed gaps. It must not invent
          qualifications or suggest adding experience the resume does not
          support.
        </p>
      </div>

      {isLoading && (
        <div aria-live="polite" className="mt-4">
          <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
            Analyzing this job…
          </p>
          <div className="mt-3 space-y-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div
                key={index}
                className="rounded-lg border border-app-border p-4"
              >
                <Skeleton className="h-3 w-20" />
                <Skeleton className="mt-3 h-4 w-2/3" />
                <Skeleton className="mt-2 h-3 w-full" />
                <Skeleton className="mt-1 h-3 w-5/6" />
              </div>
            ))}
          </div>
        </div>
      )}

      {!isLoading && error && (
        <div
          role="alert"
          className="mt-4 rounded-lg border border-app-danger-border bg-app-danger-bg p-4"
        >
          <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-app-red">
            Gap analysis unavailable
          </div>
          <p className="mt-2 text-xs leading-5 text-app-danger-text">
            {error} The rest of this job&apos;s details remain available.
          </p>
          <div className="mt-3">
            <AppButton
              variant="secondary"
              size="sm"
              onClick={() => onCalculate(jobId)}
            >
              Retry
            </AppButton>
          </div>
        </div>
      )}

      {!isLoading && !error && result && gapCount === 0 && (
        <div className="mt-4 rounded-lg border border-app-border p-4 text-center">
          <p className="text-sm font-semibold text-app-text">
            No meaningful gaps found
          </p>
          <p className="mt-1 text-xs leading-5 text-app-faint">
            No job-specific gaps were identified for this resume.
          </p>
        </div>
      )}

      {!isLoading && !error && result && gapCount > 0 && (
        <ul className="mt-4 space-y-3">
          {gaps.map((gap, index) => (
            <GapSuggestionCard
              key={gap.requirement_id || index}
              gap={gap}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function GapSuggestionCard({ gap }: { gap: GapSuggestion }) {
  const isImprove = gap.status === "partial";
  const typeLabel = isImprove ? "Improve" : "Missing";
  const icon = isImprove ? "◐" : "✕";
  const colorClass = isImprove ? "text-app-blue" : "text-app-red";

  const title = gap.requirement_text?.trim() || "Unspecified requirement";
  const explanation =
    gap.explanation?.trim() || "No explanation was provided for this gap.";
  const jdEvidence =
    gap.jd_evidence?.trim() || "Not specified in the job description.";
  const resumeEvidence = gap.resume_evidence?.trim();
  const suggestionText = gap.suggestion_text?.trim();
  const confidence = gap.confidence || "unknown";

  return (
    <li className="rounded-lg border border-app-border p-4">
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className={`mt-0.5 shrink-0 ${colorClass}`}
        >
          {icon}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`font-mono text-[9px] font-semibold uppercase tracking-[0.12em] ${colorClass}`}
            >
              {typeLabel}
            </span>

            {gap.suggestion_type && (
              <span className="font-mono text-[8px] uppercase tracking-[0.1em] text-app-faint">
                {formatSuggestionType(gap.suggestion_type)}
              </span>
            )}
          </div>

          <h4 className="mt-1 text-sm font-semibold text-app-text">
            {title}
          </h4>

          <p className="mt-2 text-xs leading-5 text-app-muted">
            {explanation}
          </p>

          {suggestionText && (
            <p className="mt-2 text-xs leading-5 text-app-text">
              <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-app-blue">
                Suggestion:{" "}
              </span>
              {suggestionText}
            </p>
          )}

          <div className="mt-3 border-t border-app-border pt-2">
            <div className="font-mono text-[8px] uppercase tracking-[0.1em] text-app-faint">
              Source
            </div>
            <p className="mt-1 text-[11px] leading-5 text-app-dim">
              Job requirement: {jdEvidence}
            </p>
            <p className="mt-0.5 text-[11px] leading-5 text-app-dim">
              {resumeEvidence
                ? `Resume evidence: ${resumeEvidence}`
                : "No resume evidence found for this requirement."}
            </p>
          </div>

          <div className="mt-2 font-mono text-[8px] uppercase tracking-[0.1em] text-app-faint">
            Confidence: {confidence}
          </div>
        </div>
      </div>
    </li>
  );
}

function formatSuggestionType(value: string): string {
  return value
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
