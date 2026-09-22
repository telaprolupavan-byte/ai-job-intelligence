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
  /** Display name of the parent version, for the Figma 09.1 version
   *  history block. Resolved by the caller from the resume-version list
   *  it already loads, so this needs no extra API field. */
  parentVersionName?: string;
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
  parentVersionName,
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
          {/* Figma 09 panel header. */}
          <p className="mt-1 break-words text-sm font-semibold text-app-text">
            Review NERO&apos;s improvement suggestions
          </p>
          <p className="mt-1 text-xs leading-5 text-app-faint">
            Approve or skip evidence-backed improvements. NERO only
            applies changes you approve.
          </p>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {gaps.length > 0 && !showCompare && (
            <Badge tone="blue-soft">
              {gaps.length} {gaps.length === 1 ? "suggestion" : "suggestions"}
            </Badge>
          )}
          {result && (
            <>
              <Badge tone="neutral-soft">
                {result.child_resume_version_name}
              </Badge>
              {result.recheck_status === "complete" && result.comparison && (
                <ScoreDeltaBadge delta={result.comparison.score_delta} />
              )}
            </>
          )}
        </div>
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

      {/* Figma 09: "Review before apply" callout, above the suggestions. */}
      <div className="mt-3 rounded-md border border-app-border px-3 py-2">
        <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-blue">
          Review before apply
        </p>
        <p className="mt-1 break-words text-[11px] leading-5 text-app-faint">
          Approve only changes you want NERO to apply. ADD IF TRUE
          requires explicit confirmation.
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
          parentVersionName={parentVersionName}
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

          {/* Figma 09: the two safety blocks sit between the suggestion
              list and the approval action. */}
          <div className="mt-4 rounded-lg border border-app-blue p-4">
            <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-blue">
              Safety and evidence
            </p>
            <p className="mt-1 break-words text-xs leading-5 text-app-body">
              NERO creates a new version only from approved,
              evidence-backed changes. Your original resume remains
              unchanged.
            </p>
          </div>

          <div className="mt-3 rounded-lg border border-app-border bg-app-panel p-4">
            <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
              NERO safety rule
            </p>
            <p className="mt-1 break-words text-[11px] leading-5 text-app-faint">
              NERO may only apply approved evidence-backed changes. ADD IF
              TRUE requires explicit user confirmation. It must never
              invent skills, experience, credentials, employers, metrics,
              or education.
            </p>
          </div>

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
      {/* Figma 09 labels each review card with the raw suggestion-type
          token, underscores intact and in blue for both types — the
          token is what the approval rules key off, so it is shown
          verbatim rather than humanized. (09.1's amber "ADD IF TRUE" is
          the *state* label on the confirmation block below, not this
          card token.) */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[9px] font-semibold uppercase tracking-[0.12em] text-app-blue">
          {gap.suggestion_type || "SUGGESTION"}
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

      {/* Figma 09: the suggestion sentence is the card's primary line,
          with the evidence note dimmed beneath it. */}
      {gap.suggestion_text && (
        <p className="mt-2 break-words text-xs leading-5 text-app-body">
          {gap.suggestion_text}
        </p>
      )}

      <p className="mt-2 break-words text-[11px] leading-5 text-app-dim">
        {gap.resume_evidence
          ? gap.resume_evidence
          : `No supporting ${title} evidence was found in the selected resume.`}
      </p>

      {/* DECISION CONTROLS */}
      <div
        role="group"
        aria-label={`Decision for ${title}`}
        className="mt-3 flex flex-wrap gap-2"
      >
        <DecisionToggle
          selected={isApproved}
          label="Approve"
          emphasis="primary"
          onClick={() => onChange({ action: "approve" })}
        />
        <DecisionToggle
          selected={decision.action === "skip"}
          label="Skip"
          emphasis="secondary"
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

          {/* Figma 09.1, "ADD IF TRUE" card: a titled confirmation block
              stating that no supporting evidence was found, then a short
              "I confirm this is true" checkbox. */}
          {needsTruth && (
            <div className="mt-3 rounded-lg border border-app-amber/40 bg-app-amber-soft/40 p-3">
              <p className="break-words text-xs font-semibold text-app-text">
                Confirm this is true for your experience
              </p>
              <p className="mt-1 break-words text-[11px] leading-5 text-app-body">
                NERO found no supporting evidence in the selected resume.
                Only continue if you genuinely used {title} in the way you
                describe above.
              </p>

              <label
                htmlFor={confirmId}
                className="mt-3 flex cursor-pointer items-start gap-2"
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
                  I confirm this is true
                </span>
              </label>
            </div>
          )}
        </div>
      )}
    </li>
  );
}

// Figma 09 gives Approve primary weight and Skip secondary weight. The
// pressed state stays a filled pill so the user can still see which of
// the two they picked — the hierarchy changes, the toggle semantics do
// not.
function DecisionToggle({
  selected,
  label,
  emphasis,
  onClick,
}: {
  selected: boolean;
  label: string;
  emphasis: "primary" | "secondary";
  onClick: () => void;
}) {
  // Only Approve ever takes the filled blue treatment. Skip is the
  // default choice, so filling it would make the no-op action the
  // loudest thing on the card — the inverse of Figma 09's hierarchy —
  // and it still reads as chosen via the neutral fill and aria-pressed.
  const className =
    emphasis === "primary"
      ? selected
        ? "border-app-blue bg-app-blue text-black"
        : "border-app-blue text-app-blue hover:bg-app-blue-soft"
      : selected
        ? "border-app-border-strong bg-app-panel-strong text-app-text"
        : "border-app-border text-app-muted hover:border-app-border-strong hover:text-app-text";

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`app-focus-ring rounded-lg border px-4 py-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.1em] transition-colors ${className}`}
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
  parentVersionName,
  isRechecking,
  onRetryRecheck,
  onReviewMore,
}: {
  jobId: string;
  result: ResumeImprovementResult;
  parentVersionName?: string;
  isRechecking: boolean;
  onRetryRecheck: (jobId: string, improvementId: string) => void;
  onReviewMore: () => void;
}) {
  const comparison = result.comparison;
  const appliedDecisions = result.decisions.filter(
    (decision) => decision.action === "approve" && decision.applied_text,
  );

  return (
    <div className="mt-4">
      {/* Figma 09: "New resume version created" — the lineage line, then
          a WHAT CHANGED list naming each approved requirement and the
          wording the user supplied for it. */}
      <div className="rounded-lg border border-app-blue p-4">
        <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-blue">
          New resume version created
        </p>
        <p className="mt-1 break-words text-xs leading-5 text-app-body">
          {result.child_resume_version_name} &middot; based on{" "}
          {parentVersionName ?? "your original version"} &middot;{" "}
          {result.approved_count} approved{" "}
          {result.approved_count === 1 ? "improvement" : "improvements"}{" "}
          applied
        </p>

        <div className="mt-3 border-t border-app-border pt-3">
          <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
            What changed
          </p>
          <ul className="mt-2 space-y-1.5">
            {appliedDecisions.length === 0 && (
              <li className="break-words text-[11px] leading-5 text-app-faint">
                No changes were applied.
              </li>
            )}
            {appliedDecisions.map((decision) => (
              <li
                key={decision.requirement_id}
                className="break-words text-[11px] leading-5 text-app-body"
              >
                <span className="text-app-text">
                  {decision.requirement_text}
                </span>{" "}
                &rarr; {decision.applied_text}
              </li>
            ))}
          </ul>
        </div>

        <p className="mt-3 break-words text-[11px] leading-5 text-app-faint">
          Your original version is untouched and still your master
          resume.
        </p>
      </div>

      {result.recheck_status !== "complete" && (
        <div
          role="status"
          className="mt-3 rounded-lg border border-app-danger-border bg-app-danger-bg p-4"
        >
          {/* Figma 09.1, "RECHECK FAILED" card: the headline leads with
              what was preserved, not with the failure, so the user's
              first read is that nothing was lost. */}
          <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-app-red">
            Recheck failed
          </div>
          <p className="mt-1 break-words text-sm font-semibold text-app-text">
            Your new resume version was preserved
          </p>
          <p className="mt-2 break-words text-xs leading-5 text-app-danger-text">
            The recheck could not complete against the same job. No
            changes were lost. You can retry the recheck without
            re-approving anything.
          </p>
          {result.recheck_error && (
            <p className="mt-2 break-words text-[11px] leading-5 text-app-danger-text">
              {result.recheck_error}
            </p>
          )}
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
          {/* Figma 09: "Recheck results" panel heading. */}
          <div className="mt-3">
            <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-blue">
              Recheck results
            </p>
            <p className="mt-1 break-words text-[11px] leading-5 text-app-faint">
              Same job &middot; new resume version &middot; compare before
              vs after
            </p>
          </div>

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
              {comparison.unchanged_count} remained
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

      {comparison && (
        <p className="mt-3 break-words text-[11px] leading-5 text-app-faint">
          Original resume version remains available in version history.
        </p>
      )}

      <VersionHistory result={result} parentVersionName={parentVersionName} />

      <div className="mt-4">
        <AppButton variant="ghost" size="sm" onClick={onReviewMore}>
          Review suggestions again
        </AppButton>
      </div>
    </div>
  );
}

// Figma 09.1, "Version history": the parent/child relationship shown as
// two cards joined by an arrow — the original labelled as unchanged and
// recoverable, the child labelled with what it was based on, how many
// approved changes it carries, and that the recheck used the same job.
function VersionHistory({
  result,
  parentVersionName,
}: {
  result: ResumeImprovementResult;
  parentVersionName?: string;
}) {
  const parentLabel = parentVersionName ?? "Original";

  return (
    <div className="mt-4">
      <h4 className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
        Version history
      </h4>

      <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-stretch">
        <div className="min-w-0 flex-1 rounded-lg border border-app-border p-3">
          <p className="break-words text-xs font-semibold text-app-text">
            {parentLabel}
          </p>
          <p className="mt-1 break-words text-[11px] leading-5 text-app-faint">
            Unchanged and recoverable
          </p>
        </div>

        <div
          aria-hidden="true"
          className="flex shrink-0 items-center justify-center text-app-success sm:px-1"
        >
          <span className="hidden sm:inline">&rarr;</span>
          <span className="sm:hidden">&darr;</span>
        </div>

        <div className="min-w-0 flex-1 rounded-lg border border-app-blue p-3">
          <p className="break-words text-xs font-semibold text-app-text">
            {result.child_resume_version_name} &middot; Approved improvement
          </p>
          <p className="mt-1 break-words text-[11px] leading-5 text-app-faint">
            Based on {parentLabel} &middot; {result.approved_count} approved{" "}
            {result.approved_count === 1 ? "change" : "changes"}
          </p>
          <p className="mt-1 break-words text-[11px] leading-5 text-app-faint">
            Recheck uses the same job
          </p>
        </div>
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
      {/* Matches the approved ATS Alignment card on this same page
          (jobs/page.tsx) exactly - `mt-2 text-3xl font-bold` with a `%`
          unit. It renders the same `overall_score` value, so rendering
          it a second way on one screen reads as two different metrics. */}
      <div className="mt-2 text-3xl font-bold text-app-text">
        {Math.round(score)}%
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

// Figma 09 "Recheck results" vocabulary: IMPROVED / REMAINED /
// DISAPPEARED / NOT DETERMINED. `regressed` keeps its own label — a
// requirement that got worse is a real outcome the engine can produce
// and folding it into REMAINED would misreport it.
const DIRECTION_LABEL: Record<RequirementTransition["direction"], string> = {
  improved: "Improved",
  unchanged: "Remained",
  regressed: "Regressed",
  added: "Not determined",
  removed: "Disappeared",
};

const DIRECTION_COLOR: Record<RequirementTransition["direction"], string> = {
  improved: "text-app-success",
  unchanged: "text-app-faint",
  regressed: "text-app-red",
  added: "text-app-faint",
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

// Figma 09.1, "APPROVAL IN PROGRESS" card: the status label, the
// "Applying approved improvement…" headline, and — emphasised — the
// reassurance that the original is untouched while the write happens.
function SubmittingState() {
  return (
    <div aria-live="polite" className="mt-4">
      <div className="rounded-lg border border-app-border p-4">
        <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-success">
          Approval in progress
        </div>
        <p className="mt-1 break-words text-sm font-semibold text-app-text">
          Applying approved improvement…
        </p>
        <p className="mt-2 break-words text-xs leading-5 text-app-faint">
          NERO is creating a new resume version from the suggestions you
          approved, then rechecking it against this job.
        </p>
        <p className="mt-2 break-words text-xs font-semibold leading-5 text-app-text">
          Original resume remains unchanged.
        </p>
      </div>

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
