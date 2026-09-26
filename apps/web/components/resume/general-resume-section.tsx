"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createGeneralAssessment,
  getGeneralAssessment,
  retryGeneralRecheck,
  submitGeneralReview,
  type GeneralAssessment,
  type GeneralImprovement,
  type GeneralReview,
  type Readiness,
  type ReviewDecisionInput,
  type SuggestionType,
} from "@/lib/general-resume";
import AppButton from "@/components/app/app-button";
import Badge from "@/components/app/badge";
import ErrorState from "@/components/app/error-state";
import { PanelSkeleton } from "@/components/app/skeleton";

// AJI-027 — General Resume Intelligence, rendered on the Resume page for
// the selected version. Uses the existing NERO application components
// (no dedicated Figma frame exists for this feature).
//
// Upload -> Validation -> General Resume Score -> Improvements ->
// Approve/Reject -> New version -> Recheck -> Updated score -> Ready.
//
// The rules below are also enforced server-side
// (apps/api/services/general_resume/engine.py); this component is the
// ergonomics, never the guarantee:
//  1. Nothing changes without an explicit approval.
//  2. NERO never writes resume content: the text box is never pre-filled.
//  3. "Add only if true" items need a truth confirmation.
//  4. The score is not job-specific and is never called an ATS score. It
//     has no bands or thresholds; readiness depends only on every
//     improvement being resolved or rejected.

type Decision = {
  action: "approve" | "reject" | null;
  truthConfirmed: boolean;
  content: string;
};

type Props = {
  versionId: string;
  /** Switch the page to another version (e.g. a newly refined one). */
  onOpenVersion: (versionId: string) => void;
};

const TYPE_LABEL: Record<SuggestionType, string> = {
  REPHRASE_EXISTING: "Rephrase",
  ADD_IF_TRUE: "Add only if true",
  ADVISORY: "Advisory",
};

function formatScore(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function formatDelta(value: number): string {
  if (value > 0) return `+${formatScore(value)}`;
  if (value < 0) return `−${formatScore(Math.abs(value))}`;
  return "±0";
}

function emptyDecision(): Decision {
  return { action: null, truthConfirmed: false, content: "" };
}

function decisionError(
  item: GeneralImprovement,
  decision: Decision,
): string | null {
  if (decision.action !== "approve") return null;
  if (!decision.content.trim()) return "Write the text you want in your resume.";
  if (item.suggestion_type === "ADD_IF_TRUE" && !decision.truthConfirmed) {
    return "Confirm this is accurate before approving.";
  }
  return null;
}

function ReadinessBadge({ readiness }: { readiness: Readiness }) {
  switch (readiness.state) {
    case "ready":
      return <Badge tone="success-soft">Resume Ready</Badge>;
    case "needs_review":
      return (
        <Badge tone="blue-soft">
          {readiness.open_count} to review
        </Badge>
      );
    case "not_valid":
      return <Badge tone="red-soft">Validation issues</Badge>;
    default:
      return <Badge tone="neutral-soft">Not assessed</Badge>;
  }
}

function ReviewOutcome({
  review,
  onOpenVersion,
  onRetry,
  retrying,
}: {
  review: GeneralReview;
  onOpenVersion: (versionId: string) => void;
  onRetry: () => void;
  retrying: boolean;
}) {
  if (!review.child_resume_version_id) {
    return (
      <div className="rounded-lg border border-app-border bg-app-bg p-4 text-sm text-app-body">
        Your review was recorded ({review.rejected_count} rejected). No new
        version was created.
      </div>
    );
  }

  const childName = review.child_resume_version_name ?? "New version";
  const comparison = review.comparison;

  return (
    <div
      className="space-y-4 rounded-lg border border-app-border bg-app-bg p-4"
      data-testid="review-outcome"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-app-body">
          <span className="font-semibold text-app-text">{childName}</span>{" "}
          was created from {review.parent_resume_version_name ?? "the previous version"}.
          The original was not changed.
        </div>

        <AppButton
          size="sm"
          variant="secondary"
          onClick={() => onOpenVersion(review.child_resume_version_id!)}
        >
          Open {childName}
        </AppButton>
      </div>

      {review.recheck_status === "failed" || review.recheck_status === "pending" ? (
        <div role="alert" className="space-y-3 text-sm text-app-body">
          <p>
            Your new version was saved. Only the recheck
            {review.recheck_status === "failed" ? " failed" : " has not run yet"}
            {review.recheck_error ? `: ${review.recheck_error}` : "."}
          </p>
          <AppButton size="sm" onClick={onRetry} loading={retrying} disabled={retrying}>
            {retrying ? "Rechecking..." : "Retry recheck"}
          </AppButton>
        </div>
      ) : comparison ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-baseline gap-3">
            <span className="font-mono text-[10px] uppercase tracking-[0.15em] text-app-faint">
              Before → After
            </span>
            <span className="text-lg font-bold text-app-text" data-testid="comparison-scores">
              {formatScore(comparison.baseline_score)} → {formatScore(comparison.recheck_score)}
            </span>
            <span
              className={
                comparison.score_delta < 0 ? "text-sm font-semibold text-app-red" : "text-sm font-semibold text-app-body"
              }
              data-testid="comparison-delta"
            >
              {formatDelta(comparison.score_delta)}
            </span>
          </div>

          <ul className="grid gap-1 text-xs text-app-muted sm:grid-cols-2">
            {comparison.components.map((component) => (
              <li key={component.key}>
                {component.label}:{" "}
                {component.before === null ? "—" : formatScore(component.before)} →{" "}
                {component.after === null ? "—" : formatScore(component.after)}
              </li>
            ))}
          </ul>

          <p className="text-xs text-app-muted">
            {comparison.resolved_count} resolved · {comparison.still_present_count} still
            present · {comparison.new_count} new
          </p>
        </div>
      ) : null}
    </div>
  );
}

export default function GeneralResumeSection({ versionId, onOpenVersion }: Props) {
  const [assessment, setAssessment] = useState<GeneralAssessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [assessing, setAssessing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});

  // Re-reads the saved assessment (readiness, latest review) after a
  // review or retry. Never computes anything.
  const refresh = useCallback(async () => {
    try {
      setAssessment(await getGeneralAssessment(versionId));
      setDecisions({});
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load the General Resume Score.");
    }
  }, [versionId]);

  useEffect(() => {
    let cancelled = false;

    getGeneralAssessment(versionId)
      .then((result) => {
        if (!cancelled) setAssessment(result);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unable to load the General Resume Score.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [versionId]);

  async function assess() {
    setAssessing(true);
    setError(null);

    try {
      setAssessment(await createGeneralAssessment(versionId));
      setDecisions({});
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to calculate the General Resume Score.");
    } finally {
      setAssessing(false);
    }
  }

  function updateDecision(id: string, patch: Partial<Decision>) {
    setDecisions((current) => ({
      ...current,
      [id]: { ...(current[id] ?? emptyDecision()), ...patch },
    }));
  }

  const improvements = assessment?.improvements ?? [];
  const decided = improvements.filter(
    (item) => decisions[item.improvement_id]?.action,
  );
  const blocked = decided.some((item) =>
    decisionError(item, decisions[item.improvement_id]),
  );
  const approvedCount = decided.filter(
    (item) => decisions[item.improvement_id].action === "approve",
  ).length;

  async function submit() {
    if (!assessment || decided.length === 0 || blocked) return;

    const payload: ReviewDecisionInput[] = decided.map((item) => {
      const decision = decisions[item.improvement_id];

      return decision.action === "approve"
        ? {
            improvement_id: item.improvement_id,
            action: "approve",
            truth_confirmed: decision.truthConfirmed,
            user_content: decision.content,
          }
        : { improvement_id: item.improvement_id, action: "reject" };
    });

    setSubmitting(true);
    setReviewError(null);

    try {
      await submitGeneralReview(versionId, assessment.id, payload);
      await refresh();
    } catch (err) {
      setReviewError(err instanceof Error ? err.message : "Unable to save your review.");
    } finally {
      setSubmitting(false);
    }
  }

  async function retry(reviewId: string) {
    setRetrying(true);
    setReviewError(null);

    try {
      await retryGeneralRecheck(reviewId);
      await refresh();
    } catch (err) {
      setReviewError(err instanceof Error ? err.message : "Unable to recheck your new version.");
    } finally {
      setRetrying(false);
    }
  }

  // Readiness is this version's own. The review outcome (refined version,
  // comparison, recheck retry) is driven by the latest review instead,
  // and never hides this version's own improvements.
  const readiness = assessment?.readiness;
  const latestReview = assessment?.latest_review ?? null;

  return (
    <section
      className="mt-8 rounded-xl border border-app-border bg-app-panel p-6"
      aria-labelledby="general-resume-heading"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-app-blue">
            General Resume Intelligence
          </div>
          <h2 id="general-resume-heading" className="mt-2 text-xl font-bold text-app-text">
            General Resume Score
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-app-muted">
            Evaluates this resume on its own. Not specific to any job, and
            not an ATS score.
          </p>
        </div>

        {readiness && <ReadinessBadge readiness={readiness} />}
      </div>

      {loading ? (
        <div className="mt-6">
          <PanelSkeleton lines={3} />
        </div>
      ) : error ? (
        <div className="mt-6">
          <ErrorState message={error} onRetry={assessment ? refresh : assess} />
        </div>
      ) : !assessment ? (
        <div className="mt-6 flex flex-wrap items-center gap-4">
          <p className="text-sm text-app-body">
            This version has not been scored yet.
          </p>
          <AppButton onClick={assess} loading={assessing} disabled={assessing}>
            {assessing ? "Scoring..." : "Get General Resume Score"}
          </AppButton>
        </div>
      ) : (
        <div className="mt-6 space-y-6">
          <div className="flex flex-wrap items-end gap-6">
            <div>
              <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
                General Resume Score
              </div>
              <div className="mt-1 text-4xl font-bold text-app-text" data-testid="general-score">
                {formatScore(assessment.overall_score)}
                <span className="ml-1 text-base font-medium text-app-muted">/ 100</span>
              </div>
            </div>
            <div className="text-xs text-app-muted">
              {assessment.resume_version_name} · equal-weight average of the
              components that could be measured
            </div>
          </div>

          {assessment.generation_status === "partial" && (
            <p className="text-xs text-app-muted" data-testid="partial-note">
              AI explanations were unavailable, so standard guidance is
              shown. The score and readiness are not affected.
            </p>
          )}

          {!assessment.validation.valid && (
            <ErrorState
              title="Validation"
              message={assessment.validation.warnings.join(" ")}
            />
          )}

          <ul className="grid gap-3 md:grid-cols-2">
            {assessment.components.map((component) => (
              <li
                key={component.key}
                className="rounded-lg border border-app-border bg-app-bg p-4"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-sm font-semibold text-app-text">
                    {component.label}
                  </span>
                  <span className="text-sm font-bold text-app-text">
                    {component.score === null ? "Not enough data" : formatScore(component.score)}
                  </span>
                </div>
                {component.score !== null && (
                  <div
                    className="mt-2 h-1.5 overflow-hidden rounded-full bg-app-surface"
                    aria-hidden="true"
                  >
                    <div
                      className="h-full rounded-full bg-app-blue"
                      style={{ width: `${component.score}%` }}
                    />
                  </div>
                )}
                <p className="mt-2 text-xs text-app-muted">{component.detail}</p>
              </li>
            ))}
          </ul>

          {latestReview?.child_resume_version_id && (
            <ReviewOutcome
              review={latestReview}
              onOpenVersion={onOpenVersion}
              onRetry={() => retry(latestReview.id)}
              retrying={retrying}
            />
          )}

          {readiness?.state === "ready" && (
            <div
              className="rounded-lg border border-app-border bg-app-bg p-4 text-sm text-app-body"
              data-testid="ready-message"
            >
              Resume Ready: every improvement for this version has been
              resolved or rejected.
            </div>
          )}

          {reviewError && <ErrorState message={reviewError} />}

          {improvements.length > 0 && (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-semibold text-app-text">Improvements</h3>
                <p className="mt-1 text-sm text-app-muted">
                  Approve an improvement by writing the text yourself, or
                  reject it. NERO never writes resume content for you.
                  Approving creates a new version; your current version is
                  never changed.
                </p>
              </div>

              <ul className="space-y-3">
                {improvements.map((item) => {
                  const decision = decisions[item.improvement_id] ?? emptyDecision();
                  const problem = decisionError(item, decision);

                  return (
                    <li
                      key={item.improvement_id}
                      className="rounded-lg border border-app-border bg-app-bg p-4"
                      data-testid="improvement"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-semibold text-app-text">
                          {item.title}
                        </span>
                        <Badge tone="neutral-soft">{TYPE_LABEL[item.suggestion_type]}</Badge>
                        {item.status === "dismissed" && (
                          <Badge tone="neutral-soft">Rejected earlier</Badge>
                        )}
                      </div>

                      {item.evidence && (
                        <blockquote className="mt-3 border-l-2 border-app-border-strong pl-3 text-sm text-app-body">
                          {item.evidence}
                        </blockquote>
                      )}

                      <p className="mt-3 text-sm text-app-body">{item.explanation}</p>
                      <p className="mt-2 text-sm text-app-muted">
                        <span className="font-semibold">Guidance: </span>
                        {item.guidance}
                        {(item.explanation_source === "ai" || item.guidance_source === "ai") && (
                          <span className="ml-2 font-mono text-[9px] uppercase tracking-wider text-app-faint">
                            AI-assisted
                          </span>
                        )}
                      </p>

                      <div className="mt-4 flex flex-wrap gap-2" role="group" aria-label={`Decision for ${item.title}`}>
                        {item.suggestion_type !== "ADVISORY" && (
                          <AppButton
                            size="sm"
                            variant={decision.action === "approve" ? "primary" : "secondary"}
                            aria-pressed={decision.action === "approve"}
                            onClick={() =>
                              updateDecision(item.improvement_id, {
                                action: decision.action === "approve" ? null : "approve",
                              })
                            }
                          >
                            Approve
                          </AppButton>
                        )}
                        <AppButton
                          size="sm"
                          variant={decision.action === "reject" ? "primary" : "ghost"}
                          aria-pressed={decision.action === "reject"}
                          onClick={() =>
                            updateDecision(item.improvement_id, {
                              action: decision.action === "reject" ? null : "reject",
                            })
                          }
                        >
                          Reject
                        </AppButton>
                      </div>

                      {decision.action === "approve" && (
                        <div className="mt-4 space-y-3">
                          <label className="block text-xs font-semibold text-app-muted">
                            {item.kind === "bullet" ? "Your replacement for this line" : "Your text to add"}
                            <textarea
                              className="mt-2 w-full rounded-lg border border-app-border-strong bg-app-panel px-3 py-2 text-sm text-app-text outline-none focus:border-app-blue"
                              rows={3}
                              value={decision.content}
                              onChange={(event) =>
                                updateDecision(item.improvement_id, { content: event.target.value })
                              }
                            />
                          </label>

                          {item.suggestion_type === "ADD_IF_TRUE" && (
                            <label className="flex items-start gap-2 text-sm text-app-body">
                              <input
                                type="checkbox"
                                className="mt-1"
                                checked={decision.truthConfirmed}
                                onChange={(event) =>
                                  updateDecision(item.improvement_id, {
                                    truthConfirmed: event.target.checked,
                                  })
                                }
                              />
                              I confirm what I wrote is accurate.
                            </label>
                          )}

                          {problem && <p className="text-xs text-app-red">{problem}</p>}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>

              <div className="flex flex-wrap items-center gap-4">
                <AppButton
                  onClick={submit}
                  loading={submitting}
                  disabled={submitting || decided.length === 0 || blocked}
                >
                  {submitting
                    ? "Saving..."
                    : approvedCount > 0
                      ? "Create new version and recheck"
                      : "Save review"}
                </AppButton>
                <span className="text-xs text-app-muted">
                  {approvedCount} approved · {decided.length - approvedCount} rejected ·{" "}
                  {improvements.length - decided.length} undecided
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
