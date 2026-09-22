"use client";

import { useMemo, useState } from "react";
import type {
  GapAnalysisResult,
  GapSuggestion,
  ImprovementDecisionInput,
  RequirementTransition,
  ResumeImprovementResult,
} from "@/lib/jobs";
import AppButton from "./app-button";
import Badge from "./badge";
import { Skeleton } from "./skeleton";

// AJI-021 — Resume Improvement Approval & Recheck (Figma section 09) and
// its responsive/interaction states (section 09.1).
//
// The full workflow this renders: Analyze (ATS Alignment) -> Review (Gap
// Analysis, rendered by GapAnalysisSection above) -> Approve/Skip (here)
// -> Create New Resume Version -> Recheck -> Compare.
//
// Three rules are visible in this file, and all three are *also*
// enforced server-side — this component is the ergonomics, never the
// guarantee (see apps/api/services/resume_improvement/engine.py):
//
//  1. Nothing is applied without an explicit per-suggestion approval.
//  2. An ADD_IF_TRUE suggestion cannot be approved until the user ticks
//     the truth-confirmation box.
//  3. NERO never writes resume content. Every approved suggestion needs
//     the user's own wording; the suggestion text is shown as advice and
//     is never pre-filled into the box that becomes resume content.

type DecisionState = {
  action: "approve" | "skip";
  truthConfirmed: boolean;
  content: string;
};

type ResumeImprovementSectionProps = {
  jobId: string;
  /** The Gap Analysis whose suggestions are under review. */
  gapAnalysis?: GapAnalysisResult;
  /** An already-created improvement, if the user has approved before. */
  result?: ResumeImprovementResult;
  isSubmitting: boolean;
  isRechecking: boolean;
  error?: string;
  onApprove: (
    jobId: string,
    gapAnalysisId: string,
    decisions: ImprovementDecisionInput[],
  ) => void;
  onRetryRecheck: (jobId: string, improvementId: string) => void;
};

const STEPS = [
  "Review",
  "Approve",
  "New version",
  "Recheck",
  "Compare",
] as const;

function emptyDecision(): DecisionState {
  return { action: "skip", truthConfirmed: false, content: "" };
}

export default function ResumeImprovementSection({
  jobId,
  gapAnalysis,
  result,
  isSubmitting,
  isRechecking,
  error,
  onApprove,
  onRetryRecheck,
}: ResumeImprovementSectionProps) {
  const gaps = gapAnalysis?.gaps ?? [];

  const [decisions, setDecisions] = useState<Record<string, DecisionState>>({});
  // After a successful cycle the Compare view is what matters; the user
  // can reopen the list to approve a different set, which creates an
  // additional version rather than replacing the one they already have.
  const [isReviewing, setIsReviewing] = useState(false);

  // Return to the comparison as soon as a submission finishes, so
  // approving from the reopened review list is not a dead end. Keyed on
  // the submission finishing rather than on the record's id changing:
  // re-approving an identical set legitimately returns the *same*
  // record (the server refuses to create a duplicate version), and that
  // still needs to land the user back on the result.
  const [wasSubmitting, setWasSubmitting] = useState(isSubmitting);

  if (isSubmitting !== wasSubmitting) {
    setWasSubmitting(isSubmitting);

    if (!isSubmitting && result && !error) {
      setIsReviewing(false);
    }
  }

  function decisionFor(requirementId: string): DecisionState {
    return decisions[requirementId] ?? emptyDecision();
  }

  function update(requirementId: string, patch: Partial<DecisionState>) {
    setDecisions((current) => ({
      ...current,
      [requirementId]: { ...decisionFor(requirementId), ...patch },
    }));
  }

  const approvedGaps = useMemo(
    () => gaps.filter((gap) => decisionFor(gap.requirement_id).action === "approve"),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [gaps, decisions],
  );

  const blockers = useMemo(() => {
    const reasons: string[] = [];

    if (approvedGaps.length === 0) {
      reasons.push("Approve at least one suggestion.");
    }

    const missingContent = approvedGaps.filter(
      (gap) => !decisionFor(gap.requirement_id).content.trim(),
    );

    if (missingContent.length > 0) {
      reasons.push(
        `Add your own wording for ${missingContent.length} approved ${
          missingContent.length === 1 ? "suggestion" : "suggestions"
        }.`,
      );
    }

    const unconfirmed = approvedGaps.filter(
      (gap) =>
        gap.suggestion_type === "ADD_IF_TRUE" &&
        !decisionFor(gap.requirement_id).truthConfirmed,
    );

    if (unconfirmed.length > 0) {
      reasons.push(
        `Confirm ${unconfirmed.length} added ${
          unconfirmed.length === 1 ? "item is" : "items are"
        } accurate.`,
      );
    }

    return reasons;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [approvedGaps, decisions]);

  const canSubmit = blockers.length === 0 && !isSubmitting;

  function handleSubmit() {
    if (!gapAnalysis || !canSubmit) return;

    onApprove(
      jobId,
      gapAnalysis.id,
      gaps.map<ImprovementDecisionInput>((gap) => {
        const decision = decisionFor(gap.requirement_id);

        if (decision.action !== "approve") {
          return { requirement_id: gap.requirement_id, action: "skip" };
        }

        return {
          requirement_id: gap.requirement_id,
          action: "approve",
          truth_confirmed: decision.truthConfirmed,
          user_content: decision.content.trim(),
        };
      }),
    );
  }

  const showCompare = Boolean(result) && !isReviewing;

  return (
    <section
      aria-labelledby={`resume-improvement-${jobId}`}
      className="mt-4 rounded-lg border border-app-border bg-app-bg p-4"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3
            id={`resume-improvement-${jobId}`}
            className="font-mono text-[9px] uppercase tracking-[0.18em] text-app-blue"
          >
            Resume Improvement
          </h3>
          <p className="mt-1 text-xs leading-5 text-app-faint">
            Approve the suggestions you want, and NERO builds a new
            version and rechecks it against this job.
          </p>
        </div>

        {result && (
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <Badge tone="neutral-soft">{result.child_resume_version_name}</Badge>
            {result.recheck_status === "complete" && result.comparison && (
              <ScoreDeltaBadge delta={result.comparison.score_delta} />
            )}
          </div>
        )}
      </div>

      <StepTrail
        active={
          showCompare
            ? result?.recheck_status === "complete"
              ? "Compare"
              : "Recheck"
            : isSubmitting
              ? "New version"
              : "Review"
        }
      />

      <div className="mt-3 rounded-md border border-app-border px-3 py-2">
        <p className="text-[11px] leading-5 text-app-faint">
          NERO never edits your resume on its own and never writes content
          for you. Your original version is always kept — approving
          creates a new version alongside it.
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="mt-4 rounded-lg border border-app-danger-border bg-app-danger-bg p-4"
        >
          <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-app-red">
            Couldn&apos;t apply your approvals
          </div>
          <p className="mt-2 break-words text-xs leading-5 text-app-danger-text">
            {error} Nothing was changed, and your notes below are still
            here.
          </p>
        </div>
      )}

      {isSubmitting && <SubmittingState />}

      {!isSubmitting && showCompare && result && (
        <CompareView
          jobId={jobId}
          result={result}
          isRechecking={isRechecking}
          onRetryRecheck={onRetryRecheck}
          onReviewMore={() => setIsReviewing(true)}
        />
      )}

      {!isSubmitting && !showCompare && !gapAnalysis && (
        <EmptyState
          title="Run Gap Analysis first"
          body="Analyze this job's gaps above, then come back to approve the suggestions you agree with."
        />
      )}

      {!isSubmitting && !showCompare && gapAnalysis && gaps.length === 0 && (
        <EmptyState
          title="Nothing to approve"
          body="No gaps were found for this resume against this job, so there is nothing to improve here."
        />
      )}

      {!isSubmitting && !showCompare && gapAnalysis && gaps.length > 0 && (
        <>
          {result && (
            <div className="mt-4 rounded-lg border border-app-border px-3 py-2">
              <p className="text-[11px] leading-5 text-app-faint">
                You already created {result.child_resume_version_name}.
                Approving a different set creates another new version —
                it never replaces that one.
              </p>
              <div className="mt-2">
                <AppButton
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsReviewing(false)}
                >
                  Back to comparison
                </AppButton>
              </div>
            </div>
          )}

          <ul className="mt-4 space-y-3">
            {gaps.map((gap) => (
              <SuggestionDecisionCard
                key={gap.requirement_id}
                gap={gap}
                decision={decisionFor(gap.requirement_id)}
                onChange={(patch) => update(gap.requirement_id, patch)}
              />
            ))}
          </ul>

          <ApprovalFooter
            approvedCount={approvedGaps.length}
            skippedCount={gaps.length - approvedGaps.length}
            blockers={blockers}
            canSubmit={canSubmit}
            isSubmitting={isSubmitting}
            onSubmit={handleSubmit}
          />
        </>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Review / approve
// ---------------------------------------------------------------------------

function SuggestionDecisionCard({
  gap,
  decision,
  onChange,
}: {
  gap: GapSuggestion;
  decision: DecisionState;
  onChange: (patch: Partial<DecisionState>) => void;
}) {
  const isApproved = decision.action === "approve";
  const needsTruth = gap.suggestion_type === "ADD_IF_TRUE";
  const title = gap.requirement_text?.trim() || "Unspecified requirement";
  const contentId = `improvement-content-${gap.requirement_id}`;
  const confirmId = `improvement-confirm-${gap.requirement_id}`;

  return (
    <li
      className={`rounded-lg border p-4 ${
        isApproved ? "border-app-blue bg-app-blue-soft/30" : "border-app-border"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`font-mono text-[9px] font-semibold uppercase tracking-[0.12em] ${
            gap.status === "partial" ? "text-app-blue" : "text-app-red"
          }`}
        >
          {gap.status === "partial" ? "Improve" : "Missing"}
        </span>
        {gap.category === "must_have" && (
          <span className="font-mono text-[8px] uppercase tracking-[0.1em] text-app-faint">
            Must have
          </span>
        )}
      </div>

      <h4 className="mt-1 break-words text-sm font-semibold text-app-text">
        {title}
      </h4>

      {gap.suggestion_text && (
        <p className="mt-2 break-words text-xs leading-5 text-app-muted">
          <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-app-blue">
            NERO suggests:{" "}
          </span>
          {gap.suggestion_text}
        </p>
      )}

      {gap.resume_evidence && (
        <p className="mt-2 break-words text-[11px] leading-5 text-app-dim">
          What your resume shows today: {gap.resume_evidence}
        </p>
      )}

      {/* DECISION CONTROLS */}
      <div
        role="group"
        aria-label={`Decision for ${title}`}
        className="mt-3 flex flex-wrap gap-2"
      >
        <DecisionToggle
          selected={isApproved}
          label="Approve"
          onClick={() => onChange({ action: "approve" })}
        />
        <DecisionToggle
          selected={decision.action === "skip"}
          label="Skip"
          onClick={() =>
            onChange({ action: "skip", truthConfirmed: false })
          }
        />
      </div>

      {isApproved && (
        <div className="mt-3">
          <label
            htmlFor={contentId}
            className="block font-mono text-[9px] uppercase tracking-[0.1em] text-app-faint"
          >
            Your wording (added to the new version)
          </label>
          <textarea
            id={contentId}
            value={decision.content}
            onChange={(event) => onChange({ content: event.target.value })}
            rows={3}
            maxLength={2000}
            placeholder={
              needsTruth
                ? `Describe your real experience with ${title} — only if it is accurate.`
                : `Rewrite your own line about ${title} in your own words.`
            }
            className="app-focus-ring mt-1 block w-full resize-y rounded-lg border border-app-border bg-app-panel px-3 py-2 text-xs leading-5 text-app-text outline-none placeholder:text-app-soft"
          />
          <p className="mt-1 text-[10px] leading-4 text-app-faint">
            Only this text is added to your resume. NERO does not write it
            for you.
          </p>

          {needsTruth && (
            <div className="mt-3 rounded-lg border border-app-amber/40 bg-app-amber-soft/40 p-3">
              <label
                htmlFor={confirmId}
                className="flex cursor-pointer items-start gap-2"
              >
                <input
                  id={confirmId}
                  type="checkbox"
                  checked={decision.truthConfirmed}
                  onChange={(event) =>
                    onChange({ truthConfirmed: event.target.checked })
                  }
                  className="app-focus-ring mt-0.5 h-4 w-4 shrink-0 accent-app-blue"
                />
                <span className="min-w-0 text-[11px] leading-5 text-app-body">
                  I confirm this is accurate and true of my own
                  experience.
                </span>
              </label>

              {!decision.truthConfirmed && (
                <p className="mt-2 text-[10px] leading-4 text-app-amber">
                  Your resume has no evidence for this yet, so it can only
                  be added once you confirm it.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </li>
  );
}

function DecisionToggle({
  selected,
  label,
  onClick,
}: {
  selected: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`app-focus-ring rounded-lg border px-4 py-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.1em] transition-colors ${
        selected
          ? "border-app-blue bg-app-blue text-black"
          : "border-app-border text-app-muted hover:border-app-border-strong hover:text-app-text"
      }`}
    >
      {label}
    </button>
  );
}

function ApprovalFooter({
  approvedCount,
  skippedCount,
  blockers,
  canSubmit,
  isSubmitting,
  onSubmit,
}: {
  approvedCount: number;
  skippedCount: number;
  blockers: string[];
  canSubmit: boolean;
  isSubmitting: boolean;
  onSubmit: () => void;
}) {
  return (
    <div className="mt-4 rounded-lg border border-app-border bg-app-panel p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
            Your decisions
          </div>
          <p className="mt-1 text-xs leading-5 text-app-text">
            {approvedCount} approved · {skippedCount} skipped
          </p>
        </div>

        <AppButton
          variant="primary"
          size="sm"
          disabled={!canSubmit}
          loading={isSubmitting}
          onClick={onSubmit}
          className="w-full sm:w-auto"
        >
          Create new version &amp; recheck
        </AppButton>
      </div>

      {blockers.length > 0 && (
        <ul
          aria-live="polite"
          className="mt-3 space-y-1 border-t border-app-border pt-3"
        >
          {blockers.map((blocker) => (
            <li
              key={blocker}
              className="break-words text-[11px] leading-5 text-app-amber"
            >
              {blocker}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Compare
// ---------------------------------------------------------------------------

function CompareView({
  jobId,
  result,
  isRechecking,
  onRetryRecheck,
  onReviewMore,
}: {
  jobId: string;
  result: ResumeImprovementResult;
  isRechecking: boolean;
  onRetryRecheck: (jobId: string, improvementId: string) => void;
  onReviewMore: () => void;
}) {
  const comparison = result.comparison;

  return (
    <div className="mt-4">
      <div className="rounded-lg border border-app-success/40 bg-app-success-soft/40 p-4">
        <p className="break-words text-sm font-semibold text-app-text">
          {result.child_resume_version_name} created
        </p>
        <p className="mt-1 break-words text-xs leading-5 text-app-faint">
          Built from {result.approved_count}{" "}
          {result.approved_count === 1 ? "approval" : "approvals"} you
          confirmed. Your original version is untouched and still your
          master resume.
        </p>
      </div>

      {result.recheck_status !== "complete" && (
        <div
          role="status"
          className="mt-3 rounded-lg border border-app-danger-border bg-app-danger-bg p-4"
        >
          <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-app-red">
            Recheck didn&apos;t finish
          </div>
          <p className="mt-2 break-words text-xs leading-5 text-app-danger-text">
            {result.recheck_error ||
              "The recheck against this job didn't complete."}{" "}
            Your new version was saved and is safe — only the comparison
            is missing.
          </p>
          <div className="mt-3">
            <AppButton
              variant="secondary"
              size="sm"
              loading={isRechecking}
              onClick={() => onRetryRecheck(jobId, result.id)}
            >
              Retry recheck
            </AppButton>
          </div>
        </div>
      )}

      {comparison && (
        <>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <ScoreCard
              label="Before"
              score={comparison.baseline_score}
              mustHaveMatched={comparison.baseline_must_have_matched}
              mustHaveTotal={comparison.baseline_must_have_total}
              preferredMatched={comparison.baseline_preferred_matched}
              preferredTotal={comparison.baseline_preferred_total}
            />
            <ScoreCard
              label="After"
              score={comparison.recheck_score}
              mustHaveMatched={comparison.recheck_must_have_matched}
              mustHaveTotal={comparison.recheck_must_have_total}
              preferredMatched={comparison.recheck_preferred_matched}
              preferredTotal={comparison.recheck_preferred_total}
              highlighted
            />
          </div>

          <p className="mt-3 text-[11px] leading-5 text-app-faint">
            Same job, same scoring — the only thing that changed is which
            resume version was analyzed.
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            <Badge tone="success-soft">
              {comparison.improved_count} improved
            </Badge>
            <Badge tone="neutral-soft">
              {comparison.unchanged_count} unchanged
            </Badge>
            {comparison.regressed_count > 0 && (
              <Badge tone="red-soft">
                {comparison.regressed_count} regressed
              </Badge>
            )}
          </div>

          <ul className="mt-3 space-y-2">
            {comparison.transitions.map((transition) => (
              <TransitionRow
                key={transition.requirement_id}
                transition={transition}
              />
            ))}
          </ul>
        </>
      )}

      <div className="mt-4">
        <AppButton variant="ghost" size="sm" onClick={onReviewMore}>
          Review suggestions again
        </AppButton>
      </div>
    </div>
  );
}

function ScoreCard({
  label,
  score,
  mustHaveMatched,
  mustHaveTotal,
  preferredMatched,
  preferredTotal,
  highlighted = false,
}: {
  label: string;
  score: number;
  mustHaveMatched: number;
  mustHaveTotal: number;
  preferredMatched: number;
  preferredTotal: number;
  highlighted?: boolean;
}) {
  return (
    <div
      className={`min-w-0 rounded-lg border p-4 ${
        highlighted ? "border-app-blue" : "border-app-border"
      }`}
    >
      <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
        {label}
      </div>
      <div className="mt-1 text-2xl font-bold text-app-text">
        {Math.round(score)}
      </div>
      <p className="mt-1 text-[11px] leading-5 text-app-dim">
        Must have {mustHaveMatched}/{mustHaveTotal} · Preferred{" "}
        {preferredMatched}/{preferredTotal}
      </p>
    </div>
  );
}

function ScoreDeltaBadge({ delta }: { delta: number }) {
  if (delta > 0) {
    return <Badge tone="success-soft">+{delta} ATS</Badge>;
  }

  if (delta < 0) {
    return <Badge tone="red-soft">{delta} ATS</Badge>;
  }

  return <Badge tone="neutral-soft">No ATS change</Badge>;
}

const DIRECTION_LABEL: Record<RequirementTransition["direction"], string> = {
  improved: "Improved",
  unchanged: "Unchanged",
  regressed: "Regressed",
  added: "New requirement",
  removed: "No longer listed",
};

const DIRECTION_COLOR: Record<RequirementTransition["direction"], string> = {
  improved: "text-app-success",
  unchanged: "text-app-faint",
  regressed: "text-app-red",
  added: "text-app-blue",
  removed: "text-app-faint",
};

function TransitionRow({ transition }: { transition: RequirementTransition }) {
  return (
    <li className="min-w-0 rounded-lg border border-app-border px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`font-mono text-[9px] font-semibold uppercase tracking-[0.1em] ${
            DIRECTION_COLOR[transition.direction]
          }`}
        >
          {DIRECTION_LABEL[transition.direction]}
        </span>
        {transition.was_approved && (
          <span className="font-mono text-[8px] uppercase tracking-[0.1em] text-app-faint">
            You approved this
          </span>
        )}
      </div>
      <p className="mt-1 break-words text-xs leading-5 text-app-text">
        {transition.requirement_text}
      </p>
      <p className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.1em] text-app-dim">
        {transition.before_status ?? "not listed"} →{" "}
        {transition.after_status ?? "not listed"}
      </p>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Shared states
// ---------------------------------------------------------------------------

function SubmittingState() {
  return (
    <div aria-live="polite" className="mt-4">
      <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
        Creating your new version and rechecking this job…
      </p>
      <div className="mt-3 space-y-3">
        {Array.from({ length: 2 }).map((_, index) => (
          <div key={index} className="rounded-lg border border-app-border p-4">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="mt-3 h-6 w-1/3" />
            <Skeleton className="mt-2 h-3 w-2/3" />
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="mt-4 rounded-lg border border-app-border p-4 text-center">
      <p className="text-sm font-semibold text-app-text">{title}</p>
      <p className="mt-1 text-xs leading-5 text-app-faint">{body}</p>
    </div>
  );
}

function StepTrail({ active }: { active: string }) {
  return (
    <ol className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1">
      {STEPS.map((step, index) => (
        <li key={step} className="flex items-center gap-2">
          {index > 0 && (
            <span aria-hidden="true" className="text-app-border-strong">
              ·
            </span>
          )}
          <span
            aria-current={step === active ? "step" : undefined}
            className={`font-mono text-[8px] uppercase tracking-[0.1em] ${
              step === active ? "text-app-blue" : "text-app-faint"
            }`}
          >
            {step}
          </span>
        </li>
      ))}
    </ol>
  );
}
