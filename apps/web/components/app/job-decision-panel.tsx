"use client";

import type {
  DecisionStage,
  JobDecision,
  NextStepKey,
  StageKey,
  StageStatus,
} from "@/lib/job-decision";
import type { AtsRequirementResult, EligibilityCheck } from "@/lib/jobs";
import AppButton from "./app-button";
import Badge from "./badge";
import NeroCharacterState from "./nero-character-state";
import Panel from "./panel";

// AJI-023 — the job decision workflow for one opened job. Renders
// buildJobDecision() (lib/job-decision.ts): an ordered view of results the
// existing engines already produced, following the Intelligence Panel
// spec in Figma "05 — NERO Intelligence Components" (evidence references,
// confidence language, clear user actions) with the NERO Character State
// component (25:50) reflecting real request activity. It shows no score
// of its own and makes no recommendation; the tracking actions it hosts
// only record what the user did, NERO never applies on their behalf.

type JobDecisionPanelProps = {
  jobId: string;
  decision: JobDecision;
  /** Name of the ResumeVersion the resume-based stages are pinned to. */
  resumeVersionLabel?: string | null;
  /** Reading this job's saved results failed; offers a retry. */
  savedResultsError?: string | null;
  onRetrySavedResults?: () => void;
  onRunStage: (key: StageKey) => void;
  onNextStep: (key: NextStepKey) => void;
  /** The job's Save / Mark as Applied controls (shared with the card). */
  trackingActions: React.ReactNode;
};

const STATUS_BADGE: Record<
  StageStatus,
  { label: string; tone: React.ComponentProps<typeof Badge>["tone"] }
> = {
  ready: { label: "Ready", tone: "success-soft" },
  attention: { label: "Review", tone: "blue-soft" },
  loading: { label: "Running", tone: "blue-soft" },
  not_started: { label: "Not run", tone: "neutral-soft" },
  blocked: { label: "Waiting", tone: "neutral-soft" },
  error: { label: "Failed", tone: "red-soft" },
};

const RUNNABLE_STAGES: StageKey[] = [
  "intelligence",
  "eligibility",
  "match",
  "ats",
  "gap",
];

const SUGGESTION_TYPE_LABELS = {
  HIGHLIGHT_EXISTING: "highlight existing",
  REPHRASE_EXISTING: "rephrase existing",
  ADD_IF_TRUE: "add only if true",
} as const;

export default function JobDecisionPanel({
  jobId,
  decision,
  resumeVersionLabel,
  savedResultsError,
  onRetrySavedResults,
  onRunStage,
  onNextStep,
  trackingActions,
}: JobDecisionPanelProps) {
  const headingId = `job-decision-${jobId}`;
  const { nextStep } = decision;

  return (
    <Panel as="section" padding="none" className="mb-5">
      <div className="p-5 sm:p-6">
        <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-app-blue">
          NERO Job Workflow
        </div>
        <h2
          id={headingId}
          className="mt-1 break-words text-lg font-semibold text-app-text"
        >
          Understand this job, then decide
        </h2>
        <p className="mt-1 max-w-3xl text-xs leading-5 text-app-faint">
          Built only from the analyses on this page. Job Match, ATS
          Alignment and Gap Analysis are separate results and are never
          combined into one score. The decision to apply is yours — NERO
          never submits applications.
        </p>

        <div className="mt-5 grid gap-5 lg:grid-cols-[140px_minmax(0,1fr)]">
          <NeroCharacterState
            state={decision.characterState}
            className="self-start border border-app-border"
          />

          <div className="min-w-0">
            <ol className="divide-y divide-app-border rounded-lg border border-app-border">
              {decision.stages.map((stage, index) => (
                <StageRow
                  key={stage.key}
                  index={index + 1}
                  stage={stage}
                  onRun={onRunStage}
                />
              ))}
            </ol>

            {resumeVersionLabel && (
              <p className="mt-2 break-words text-[11px] leading-5 text-app-faint">
                Resume-based results use{" "}
                <span className="text-app-body">{resumeVersionLabel}</span>.
              </p>
            )}

            {savedResultsError && (
              <div
                role="alert"
                className="mt-2 flex flex-col gap-2 rounded-md border border-app-danger-border bg-app-danger-bg px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
              >
                <p className="text-[11px] leading-5 text-app-danger-text">
                  Couldn&apos;t load your saved results for this job:{" "}
                  {savedResultsError}
                </p>
                {onRetrySavedResults && (
                  <AppButton
                    variant="secondary"
                    size="sm"
                    onClick={onRetrySavedResults}
                  >
                    Retry
                  </AppButton>
                )}
              </div>
            )}

            {decision.resumeVersionMismatch && (
              <p className="mt-2 text-[11px] leading-5 text-app-danger-text">
                Job Match, ATS Alignment and Gap Analysis on this page were
                calculated for different resume versions. Recalculate them
                for one version before comparing.
              </p>
            )}

            {decision.gapBasedOnOtherAts && (
              <p className="mt-2 text-[11px] leading-5 text-app-danger-text">
                This Gap Analysis was built from an earlier ATS Alignment
                result. Recalculate Gap Analysis to match the ATS result
                shown.
              </p>
            )}

            <RelationshipNote />
          </div>
        </div>

        {nextStep && (
          <div className="mt-5 flex flex-col gap-3 rounded-lg border border-app-border bg-app-bg p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
                Next step in the workflow
              </div>
              <p className="mt-1 text-sm font-semibold text-app-text">
                {nextStep.label}
              </p>
              <p className="mt-0.5 text-xs leading-5 text-app-faint">
                {nextStep.description}
              </p>
            </div>

            {nextStep.key === "upload_resume" ? (
              <AppButton variant="secondary" size="sm" href="/resume">
                Go to Resume
              </AppButton>
            ) : nextStep.key === "save_job" ||
              nextStep.key === "mark_applied" ||
              nextStep.key === "view_application" ? null : (
              <AppButton
                variant="secondary"
                size="sm"
                onClick={() => onNextStep(nextStep.key)}
              >
                {nextStep.label}
              </AppButton>
            )}
          </div>
        )}

        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <RequirementColumn
            title="Where your resume aligns"
            tone="blue"
            items={decision.alignmentAreas}
            empty={
              hasAts(decision)
                ? "No requirements are clearly demonstrated yet."
                : "Available after ATS Alignment."
            }
          />
          <RequirementColumn
            title="Partial or missing"
            tone="red"
            items={[
              ...decision.missingRequirements,
              ...decision.partialRequirements,
            ]}
            empty={
              hasAts(decision)
                ? "No partial or missing requirements."
                : "Available after ATS Alignment."
            }
          />
          <EligibilityColumn
            blockers={decision.eligibilityBlockers}
            unknowns={decision.eligibilityUnknowns}
            checked={
              decision.stages.find((stage) => stage.key === "eligibility")
                ?.status !== "not_started"
            }
          />
          <ResumeActionsColumn decision={decision} />
        </div>

        <div className="mt-5 flex flex-col gap-3 rounded-lg border border-app-border bg-app-bg p-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-blue">
              Application Tracking
            </div>
            <p className="mt-1 max-w-xl text-xs leading-5 text-app-faint">
              Save this job to track it, or mark it applied after you apply
              on the employer&apos;s site. These only record what you did —
              NERO never submits an application for you.
            </p>
          </div>
          <div className="shrink-0">{trackingActions}</div>
        </div>
      </div>
    </Panel>
  );
}

function hasAts(decision: JobDecision): boolean {
  const ats = decision.stages.find((stage) => stage.key === "ats");
  return ats?.status === "ready";
}

function StageRow({
  index,
  stage,
  onRun,
}: {
  index: number;
  stage: DecisionStage;
  onRun: (key: StageKey) => void;
}) {
  const badge = STATUS_BADGE[stage.status];
  const canRun =
    RUNNABLE_STAGES.includes(stage.key) &&
    (stage.status === "not_started" || stage.status === "error");

  return (
    <li className="flex flex-col gap-2 px-3 py-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <div className="flex min-w-0 items-start gap-3">
        <span
          aria-hidden="true"
          className="mt-0.5 w-4 shrink-0 font-mono text-[10px] text-app-faint"
        >
          {index}
        </span>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-app-text">
            {stage.label}
          </div>
          <p
            className={`mt-0.5 break-words text-xs leading-5 ${
              stage.status === "error"
                ? "text-app-danger-text"
                : "text-app-faint"
            }`}
          >
            {stage.summary}
          </p>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 pl-7 sm:pl-0">
        <Badge tone={badge.tone}>{badge.label}</Badge>
        {canRun && (
          <AppButton
            variant="ghost"
            size="sm"
            onClick={() => onRun(stage.key)}
            aria-label={`${stage.status === "error" ? "Retry" : "Run"} ${stage.label}`}
          >
            {stage.status === "error" ? "Retry" : "Run"}
          </AppButton>
        )}
      </div>
    </li>
  );
}

function RelationshipNote() {
  return (
    <div className="mt-3 rounded-md border border-app-border px-3 py-2">
      <p className="text-[11px] leading-5 text-app-faint">
        <span className="text-app-body">Job Match</span> — how the job fits
        your profile overall. <span className="text-app-body">ATS Alignment</span>{" "}
        — how your resume reads against this job description.{" "}
        <span className="text-app-body">Gap Analysis</span> is built from the
        ATS result&apos;s missing and partial requirements, and{" "}
        <span className="text-app-body">Resume Improvement</span> works only
        from those gaps.
      </p>
    </div>
  );
}

function ColumnShell({
  title,
  tone,
  children,
}: {
  title: string;
  tone: "blue" | "red";
  children: React.ReactNode;
}) {
  return (
    <div className="min-w-0 rounded-lg border border-app-border bg-app-bg p-4">
      <h3
        className={`font-mono text-[9px] uppercase tracking-[0.15em] ${
          tone === "red" ? "text-app-red" : "text-app-blue"
        }`}
      >
        {title}
      </h3>
      {children}
    </div>
  );
}

const MAX_ITEMS = 5;

function RequirementColumn({
  title,
  tone,
  items,
  empty,
}: {
  title: string;
  tone: "blue" | "red";
  items: AtsRequirementResult[];
  empty: string;
}) {
  return (
    <ColumnShell title={title} tone={tone}>
      {items.length === 0 ? (
        <p className="mt-3 text-xs leading-5 text-app-faint">{empty}</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {items.slice(0, MAX_ITEMS).map((item) => (
            <li key={item.requirement_id} className="text-xs">
              <div className="break-words font-medium text-app-text">
                {item.requirement_text}
              </div>
              <div className="mt-0.5 font-mono text-[8px] uppercase tracking-[0.1em] text-app-faint">
                {item.category === "must_have" ? "Must-have" : "Preferred"} ·{" "}
                {item.status} · {item.confidence} confidence
              </div>
            </li>
          ))}
          {items.length > MAX_ITEMS && (
            <li className="text-[11px] text-app-faint">
              +{items.length - MAX_ITEMS} more in ATS Alignment below
            </li>
          )}
        </ul>
      )}
    </ColumnShell>
  );
}

function EligibilityColumn({
  blockers,
  unknowns,
  checked,
}: {
  blockers: EligibilityCheck[];
  unknowns: EligibilityCheck[];
  checked: boolean;
}) {
  const items = [...blockers, ...unknowns];

  return (
    <ColumnShell title="Eligibility" tone={blockers.length ? "red" : "blue"}>
      {!checked ? (
        <p className="mt-3 text-xs leading-5 text-app-faint">
          Not checked yet.
        </p>
      ) : items.length === 0 ? (
        <p className="mt-3 text-xs leading-5 text-app-faint">
          No configured hard requirement rules this job out.
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {items.slice(0, MAX_ITEMS).map((check) => (
            <li key={check.constraint} className="text-xs">
              <div className="font-mono text-[8px] uppercase tracking-[0.1em] text-app-faint">
                {check.status === "fail" ? "Blocker" : "Unverified"} ·{" "}
                {check.constraint.replace(/_/g, " ")}
              </div>
              <p className="mt-0.5 break-words leading-5 text-app-text">
                {check.reason}
              </p>
            </li>
          ))}
        </ul>
      )}
    </ColumnShell>
  );
}

function ResumeActionsColumn({ decision }: { decision: JobDecision }) {
  const actions = decision.resumeActions;

  return (
    <ColumnShell title="Resume actions" tone="blue">
      {!actions ? (
        <p className="mt-3 text-xs leading-5 text-app-faint">
          Available after Gap Analysis.
        </p>
      ) : actions.total === 0 ? (
        <p className="mt-3 text-xs leading-5 text-app-faint">
          No job-specific suggestions for this resume.
        </p>
      ) : (
        <>
          <p className="mt-3 text-xs leading-5 text-app-text">
            {actions.total}{" "}
            {actions.total === 1 ? "suggestion" : "suggestions"} to review
          </p>
          <ul className="mt-2 space-y-1">
            {(
              Object.keys(SUGGESTION_TYPE_LABELS) as Array<
                keyof typeof SUGGESTION_TYPE_LABELS
              >
            )
              .filter((type) => actions.byType[type] > 0)
              .map((type) => (
                <li
                  key={type}
                  className="font-mono text-[9px] uppercase tracking-[0.1em] text-app-faint"
                >
                  {actions.byType[type]} · {SUGGESTION_TYPE_LABELS[type]}
                </li>
              ))}
          </ul>
          <p className="mt-2 text-[11px] leading-5 text-app-faint">
            {actions.improvementCreated
              ? "You've created an improved version — see Resume Improvement below."
              : "Nothing changes until you approve it in Resume Improvement below."}
          </p>
        </>
      )}
    </ColumnShell>
  );
}
