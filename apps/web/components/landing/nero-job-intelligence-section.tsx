import type { CSSProperties } from "react";
import Link from "next/link";
import {
  BarChart3,
  FileCheck2,
  FileText,
  Lightbulb,
  Link2,
  Search,
  RefreshCcw,
  Sparkles,
  Target,
  User,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import NeroJobIntelligenceVisual from "@/components/landing/nero-job-intelligence-visual";
import SectionHeading from "@/components/landing/section-heading";

const inputPanels: {
  icon: LucideIcon;
  title: string;
  lines: string[];
}[] = [
  {
    icon: FileText,
    title: "Job Description",
    lines: ["Requirements", "Responsibilities", "Company Goals"],
  },
  {
    icon: FileCheck2,
    title: "Your Resume",
    lines: ["Experience", "Skills", "Achievements"],
  },
  {
    icon: BarChart3,
    title: "Your Skills",
    lines: ["Technical Skills", "Tools & Technologies", "Domain Knowledge"],
  },
  {
    icon: User,
    title: "Your Preferences",
    lines: ["Location", "Work Type", "Career Goals"],
  },
];

const resolutionSteps: { icon: LucideIcon; title: string }[] = [
  { icon: Target, title: "Match" },
  { icon: Sparkles, title: "Improve" },
  { icon: RefreshCcw, title: "Recheck" },
];

const principles: {
  icon: LucideIcon;
  title: string;
  text: string;
}[] = [
  {
    icon: Search,
    title: "UNDERSTAND",
    text: "NERO interprets what the opportunity actually requires.",
  },
  {
    icon: Link2,
    title: "CONNECT",
    text: "NERO connects those requirements to your background.",
  },
  {
    icon: Lightbulb,
    title: "CLARIFY",
    text: "NERO turns complexity into information you can act on.",
  },
];

const PROGRESS_STEPS = ["01", "02", "03", "04", "05", "06"];
const ACTIVE_STEP = "04";

/**
 * Page 4 — "Know Before You Apply." (Job Intelligence).
 *
 * Same world as the hero/system sections above it: the same
 * background, technical grid, atmospheric lighting, NERO figure,
 * type scale, and micro-labels, just the next scene in the scroll —
 * four conceptual inputs resolving into a single clearer
 * understanding. Built in distinct layers (background / environment /
 * inputs / streams / NERO / clarity object / foreground details) so
 * scroll-driven parallax can target each one independently.
 *
 * STRONG motion tier. The "inputs converging on NERO" idea is kept,
 * but the horizontal drift now sits on the panel *stack*, not on each
 * panel: four different data-parallax-x values meant the four panels
 * sat at four different left edges at every scroll position, so a
 * column that should read as one stack of inputs looked like a
 * mis-built flex layout. One wrapper drifting as a unit says the same
 * thing and keeps the stack aligned. Below lg, where NERO sits above
 * the stack rather than beside it, the drift is switched off entirely
 * (data-parallax-desktop-only) — there it was just a few pixels of
 * horizontal jitter with nothing to converge on.
 */
export default function NeroJobIntelligenceSection() {
  return (
    <section
      id="job-intelligence"
      className="relative overflow-hidden border-t border-white/10 bg-[#0b0e14]"
    >
      {/* Layer 1 — background */}
      <div className="technical-grid absolute inset-0 opacity-30" aria-hidden="true" />
      <div
        data-parallax-speed="0.06"
        data-parallax-local
        className="job-intel-atmosphere absolute inset-0"
        aria-hidden="true"
      />

      {/* Layer 2 — environment (subtle architectural shapes) */}
      <div
        data-parallax-speed="0.1"
        data-parallax-local
        className="pointer-events-none absolute -left-40 top-24 hidden h-[440px] w-[440px] rounded-full border border-white/5 bg-[radial-gradient(circle_at_60%_40%,rgba(10,132,255,0.08),transparent_62%)] lg:block"
        aria-hidden="true"
      />
      <div
        data-parallax-speed="0.15"
        data-parallax-local
        className="pointer-events-none absolute right-[8%] top-16 hidden h-px w-32 rotate-[28deg] bg-gradient-to-r from-transparent via-app-red/50 to-transparent lg:block"
        aria-hidden="true"
      />

      <div className="landing-shell landing-band">
        {/* Header. The handwritten "More Clarity. Brighter Careers."
            annotation used to be absolutely positioned against the
            section's own top edge, above the band padding, so its
            first line was cropped by the section boundary. It now
            sits inside the header row, opposite the copy. */}
        <div className="flex items-start justify-between gap-8">
          <SectionHeading
            eyebrow="JOB INTELLIGENCE"
            title={
              <>
                KNOW BEFORE
                <br />
                YOU{" "}
                <span className="bg-gradient-to-r from-[#8fdcff] via-[#5cc6ff] to-app-blue bg-clip-text text-transparent">
                  APPLY.
                </span>
              </>
            }
            lede="NERO brings the pieces together so you can understand an opportunity before deciding what to do next."
            className="max-w-2xl"
          />

          <div
            data-parallax-speed="0.1"
            data-parallax-local
            className="pointer-events-none hidden max-w-[180px] shrink-0 -rotate-2 pt-2 text-right lg:block"
            aria-hidden="true"
          >
            <p className="nero-note text-app-text/90">
              More
              <br />
              Clarity.
              <br />
              Brighter
              <br />
              Careers.
            </p>
          </div>
        </div>

        {/* Layer 3/4/5 — input panels, data streams, NERO */}
        <div className="job-intel-grid stack-xl">
          {/* One drift wrapper for the whole stack — the panels move
              toward NERO together instead of shearing apart. */}
          <div
            data-parallax-x="0.05"
            data-parallax-local
            data-parallax-desktop-only
            className="job-intel-area-panels flex flex-col gap-3.5"
          >
            {inputPanels.map((panel, index) => (
              <InputPanel key={panel.title} {...panel} index={index} />
            ))}
          </div>

          <div
            data-parallax-speed="0.12"
            data-parallax-scale-to="1.04"
            data-parallax-local
            className="job-intel-area-nero relative flex items-center justify-center py-2 lg:py-0"
          >
            <DataStreams />
            <NeroJobIntelligenceVisual />
          </div>

          <div
            data-parallax-speed="0.1"
            data-parallax-local
            className="job-intel-area-clarity flex justify-center"
          >
            <ClarityObject />
          </div>
        </div>

        {/* Resolution — the scene explicitly resolving into Match / */}
        {/* Improve / Recheck, per the approved Job Intelligence story. */}
        <div
          data-reveal
          className="stack-lg flex flex-wrap items-center justify-center gap-x-3 gap-y-3"
        >
          {resolutionSteps.map((step, index) => (
            <SequenceChip
              key={step.title}
              icon={step.icon}
              title={step.title}
              showConnector={index > 0}
            />
          ))}
        </div>

        {/* Three principles, with the handwritten annotation carried
            into the same band instead of floating alone in a 160px
            empty strip of its own. */}
        <div className="stack-xl border-t border-white/10 pt-[var(--stack-lg)]">
          <p
            className="nero-note hidden max-w-[260px] -rotate-2 text-app-blue lg:block"
            aria-hidden="true"
          >
            Better Decisions, Brighter Tomorrows.
          </p>

          <div className="grid grid-cols-1 gap-8 sm:grid-cols-3 sm:gap-6 lg:mt-10">
            {principles.map((principle, index) => (
              <PrincipleCard key={principle.title} {...principle} index={index} />
            ))}
          </div>
        </div>

        {/* Final marketing moment for this scene. */}
        <div
          data-reveal
          style={{ "--reveal-distance": "20px" } as CSSProperties}
          className="stack-xl relative mx-auto max-w-[980px] overflow-hidden rounded-3xl border border-white/10"
        >
          <div className="red-atmosphere absolute inset-0" aria-hidden="true" />

          <div className="relative flex flex-col items-center px-6 py-12 text-center sm:px-10 sm:py-14">
            <h3 className="display-section max-w-2xl">
              DON&apos;T APPLY{" "}
              <span className="bg-gradient-to-r from-[#8fdcff] via-[#5cc6ff] to-app-blue bg-clip-text text-transparent">
                BLIND.
              </span>
            </h3>

            <p className="section-lede mt-4 text-center">
              Understand first. Decide with confidence.
            </p>

            <Link
              href="/register"
              className="app-focus-ring group mt-8 inline-flex items-center justify-center gap-2 rounded-lg bg-crimson-fill px-6 py-3.5 text-sm font-medium text-white shadow-[0_0_28px_rgba(217,40,31,0.4)] transition hover:bg-crimson-fill-hover"
            >
              See What NERO Can Do
              <span className="transition-transform group-hover:translate-x-1">
                →
              </span>
            </Link>
          </div>
        </div>

        {/* Foreground detail — bottom utility rail. The scroll cue that
            used to sit in the middle of this row is gone; the page has
            one, in the hero. */}
        <div className="stack-lg flex flex-col items-center gap-5 border-t border-white/5 pt-6 text-center sm:flex-row sm:justify-between sm:text-left">
          <ProgressRail />

          <div className="mono text-[9px] leading-5 tracking-[0.2em] text-app-muted sm:text-right">
            SAME YOU.
            <br />
            A BRIGHTER TOMORROW.
          </div>
        </div>
      </div>
    </section>
  );
}

function SequenceChip({
  icon: Icon,
  title,
  showConnector,
}: {
  icon: LucideIcon;
  title: string;
  showConnector: boolean;
}) {
  return (
    <span className="inline-flex items-center gap-3">
      {/* Connector renders BEFORE the chip it joins, never after — a
          trailing separator was left dangling at the end of a wrapped
          line at narrow widths, which read as a broken component. */}
      {showConnector && (
        <span className="h-px w-6 bg-app-border-strong" aria-hidden="true" />
      )}
      <span className="inline-flex items-center gap-2 rounded-full border border-app-border-soft bg-app-panel/70 px-4 py-2">
        <Icon className="h-3.5 w-3.5 text-app-blue" aria-hidden="true" />
        <span className="mono text-[10px] tracking-[0.2em] text-app-text">
          {title.toUpperCase()}
        </span>
      </span>
    </span>
  );
}

function InputPanel({
  icon: Icon,
  title,
  lines,
  index,
}: {
  icon: LucideIcon;
  title: string;
  lines: string[];
  index: number;
}) {
  return (
    <div
      data-reveal
      data-reveal-delay={index * 100}
      style={{ "--reveal-distance": "14px" } as CSSProperties}
      className="glass-panel relative rounded-2xl border border-app-border-soft p-4 shadow-[0_0_24px_-14px_rgba(10,132,255,0.5)]"
    >
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-app-blue/50 bg-app-surface/80 text-app-blue">
          <Icon className="h-4 w-4" aria-hidden="true" />
        </div>

        <div className="min-w-0">
          <h3 className="text-sm font-semibold leading-5 text-app-text">
            {title}
          </h3>

          <div className="mt-1.5 space-y-0.5">
            {lines.map((line) => (
              <p key={line} className="text-xs leading-5 text-app-muted">
                {line}
              </p>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function DataStreams() {
  return (
    <svg
      className="pointer-events-none absolute inset-0 hidden h-full w-full lg:block"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="job-intel-stream-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#0a84ff" stopOpacity="0.7" />
          <stop offset="55%" stopColor="#0a84ff" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#ff3b30" stopOpacity="0.3" />
        </linearGradient>
      </defs>

      <path
        className="job-intel-streams job-intel-streams-animated"
        d="M -8 12 C 25 12, 30 48, 50 50"
        vectorEffect="non-scaling-stroke"
      />
      <path
        className="job-intel-streams job-intel-streams-animated"
        d="M -8 38 C 20 38, 35 49, 50 50"
        vectorEffect="non-scaling-stroke"
      />
      <path
        className="job-intel-streams job-intel-streams-animated"
        d="M -8 62 C 20 62, 35 51, 50 50"
        vectorEffect="non-scaling-stroke"
      />
      <path
        className="job-intel-streams job-intel-streams-animated"
        d="M -8 88 C 25 88, 30 52, 50 50"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

function ClarityObject() {
  return (
    <div
      data-scroll-progress
      className="cine-focal relative flex h-48 w-48 shrink-0 items-center justify-center sm:h-52 sm:w-52"
    >
      <div
        className="job-intel-clarity-pulse absolute inset-0 rotate-45 rounded-[2.5rem] border border-app-blue/55 bg-gradient-to-br from-app-blue/16 via-app-panel/30 to-app-blue/22 backdrop-blur-sm"
        aria-hidden="true"
      />
      <div
        className="absolute inset-8 rotate-45 rounded-[1.75rem] border border-white/15"
        aria-hidden="true"
      />

      <p
        className="relative z-10 max-w-[150px] text-center font-[family-name:var(--font-display)] text-base font-semibold leading-tight text-app-text"
        role="img"
        aria-label="A clearer understanding — NERO's abstract representation of resolved job intelligence"
      >
        A Clearer
        <br />
        <span className="bg-gradient-to-r from-[#8fdcff] to-app-blue bg-clip-text text-transparent">
          Understanding
        </span>
      </p>
    </div>
  );
}

function PrincipleCard({
  icon: Icon,
  title,
  text,
  index,
}: {
  icon: LucideIcon;
  title: string;
  text: string;
  index: number;
}) {
  return (
    <div
      data-reveal
      data-reveal-delay={index * 110}
      className="flex flex-col items-center text-center sm:items-start sm:text-left"
    >
      <div className="flex h-11 w-11 items-center justify-center rounded-full border border-app-border-soft text-app-blue">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </div>

      <h3 className="mt-4 text-xs font-semibold tracking-[0.18em] text-app-text">
        {title}
      </h3>

      <p className="mt-2 max-w-[300px] text-sm leading-6 text-app-muted">
        {text}
      </p>
    </div>
  );
}

function ProgressRail() {
  const activeIndex = PROGRESS_STEPS.indexOf(ACTIVE_STEP);
  const activePercent = (activeIndex / (PROGRESS_STEPS.length - 1)) * 100;

  return (
    <div className="flex flex-col items-center gap-2.5 sm:items-start" aria-hidden="true">
      <div className="relative h-px w-40 bg-app-border-soft">
        <span
          className="absolute -top-[3px] h-[7px] w-[7px] -translate-x-1/2 rounded-full bg-gradient-to-r from-app-blue to-[#8fdcff] shadow-[0_0_10px_rgba(10,132,255,0.7)]"
          style={{ left: `${activePercent}%` }}
        />
      </div>

      <div className="flex items-center gap-3">
        {PROGRESS_STEPS.map((step) => (
          <span
            key={step}
            className={cn(
              "mono text-[10px] tracking-[0.1em]",
              step === ACTIVE_STEP ? "text-app-text" : "text-app-muted/50",
            )}
          >
            {step}
          </span>
        ))}
      </div>
    </div>
  );
}
