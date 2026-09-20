import Link from "next/link";
import {
  BarChart3,
  ChevronDown,
  FileCheck2,
  FileText,
  Lightbulb,
  Link2,
  Mouse,
  RefreshCcw,
  Search,
  Sparkles,
  Target,
  User,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import NeroJobIntelligenceVisual from "@/components/app/nero-job-intelligence-visual";

// The first two panels — Job Description and Your Resume — are the pair
// the section's parallax is built around (spec: "Resume and job
// description move toward NERO"), so they carry a noticeably larger
// horizontal convergence speed than the supporting Skills/Preferences
// panels.
const inputPanels: {
  icon: LucideIcon;
  title: string;
  lines: string[];
  parallaxX: number;
}[] = [
  {
    icon: FileText,
    title: "Job Description",
    lines: ["Requirements", "Responsibilities", "Company Goals"],
    parallaxX: 0.075,
  },
  {
    icon: FileCheck2,
    title: "Your Resume",
    lines: ["Experience", "Skills", "Achievements"],
    parallaxX: 0.075,
  },
  {
    icon: BarChart3,
    title: "Your Skills",
    lines: ["Technical Skills", "Tools & Technologies", "Domain Knowledge"],
    parallaxX: 0.035,
  },
  {
    icon: User,
    title: "Your Preferences",
    lines: ["Location", "Work Type", "Career Goals"],
    parallaxX: 0.035,
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
 * Parallax reuses the site-wide ParallaxController: the Job
 * Description and Your Resume panels drift horizontally toward NERO
 * as the page scrolls (data-parallax-x) — motion standing in for
 * "these two are the pair being matched" — while NERO and the clarity
 * object carry their own, slower depth layers (data-parallax-speed).
 * The Match / Improve / Recheck strip is the scene's explicit
 * resolution, revealed once the clarity object is in view.
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
        className="pointer-events-none absolute -left-40 top-24 hidden h-[440px] w-[440px] rounded-full border border-white/5 bg-[radial-gradient(circle_at_60%_40%,rgba(122,92,255,0.08),transparent_62%)] lg:block"
        aria-hidden="true"
      />
      <div
        data-parallax-speed="0.15"
        data-parallax-local
        className="pointer-events-none absolute right-[8%] top-16 hidden h-px w-32 rotate-[28deg] bg-gradient-to-r from-transparent via-app-red/50 to-transparent lg:block"
        aria-hidden="true"
      />

      <div className="relative mx-auto max-w-[1536px] px-6 py-16 sm:px-10 sm:py-20 lg:px-20 lg:py-28">
        {/* Foreground detail — top-right handwritten annotation */}
        <div
          data-parallax-speed="0.12"
          data-parallax-local
          className="pointer-events-none absolute right-6 top-10 z-20 hidden max-w-[180px] -rotate-2 text-right sm:right-10 lg:right-20 lg:block"
          aria-hidden="true"
        >
          <p className="font-[family-name:var(--font-caveat)] text-2xl leading-[1.15] text-app-text/90">
            More
            <br />
            Clarity.
            <br />
            Brighter
            <br />
            Careers.
          </p>
        </div>

        {/* Header */}
        <div className="max-w-2xl">
          <div className="flex items-center gap-3">
            <span className="mono text-[10px] tracking-[0.3em] text-app-red">
              04 / 06 &nbsp; JOB INTELLIGENCE
            </span>
            <span className="h-px w-12 bg-app-red/50" />
          </div>

          <h2 className="mt-5 font-[family-name:var(--font-display)] text-[clamp(2.5rem,5.5vw,4rem)] font-extrabold leading-[0.95] tracking-[-0.03em] text-app-text">
            KNOW BEFORE
            <br />
            YOU{" "}
            <span className="bg-gradient-to-r from-[#5cc6ff] via-[#8f7bff] to-[#b46bff] bg-clip-text text-transparent">
              APPLY.
            </span>
          </h2>

          <p className="mt-6 max-w-[540px] text-base leading-7 text-app-muted sm:text-lg">
            NERO brings the pieces together so you can understand an
            opportunity before deciding what to do next.
          </p>
        </div>

        {/* Layer 3/4/5 — input panels, data streams, NERO */}
        <div className="job-intel-grid mt-16 lg:mt-20">
          <div className="job-intel-area-panels flex flex-col gap-4">
            {inputPanels.map((panel, index) => (
              <InputPanel key={panel.title} {...panel} index={index} />
            ))}
          </div>

          <div
            data-parallax-speed="0.14"
            data-parallax-scale-to="1.05"
            data-parallax-local
            className="job-intel-area-nero relative flex items-center justify-center py-4 lg:py-0"
          >
            <DataStreams />
            <NeroJobIntelligenceVisual />
          </div>

          <div
            data-parallax-speed="0.11"
            data-parallax-scale-to="1.08"
            data-parallax-local
            className="job-intel-area-clarity flex justify-center lg:justify-end"
          >
            <ClarityObject />
          </div>
        </div>

        {/* Resolution — the scene explicitly resolving into Match / */}
        {/* Improve / Recheck, per the approved Job Intelligence story. */}
        <div
          data-reveal
          className="mt-14 flex flex-wrap items-center justify-center gap-3 lg:mt-16"
        >
          {resolutionSteps.map((step, index) => (
            <div key={step.title} className="flex items-center gap-3">
              <span className="inline-flex items-center gap-2 rounded-full border border-app-border-soft bg-app-panel/70 px-4 py-2">
                <step.icon className="h-3.5 w-3.5 text-app-blue" aria-hidden="true" />
                <span className="mono text-[10px] tracking-[0.2em] text-app-text">
                  {step.title.toUpperCase()}
                </span>
              </span>
              {index < resolutionSteps.length - 1 && (
                <span className="h-px w-6 bg-app-border-strong" aria-hidden="true" />
              )}
            </div>
          ))}
        </div>

        {/* Foreground detail — handwritten annotation, own row so it never
            collides with the input panels or principle cards above/below. */}
        <div
          className="mt-16 hidden max-w-[220px] -rotate-2 lg:mt-20 lg:block"
          aria-hidden="true"
        >
          <p className="font-[family-name:var(--font-caveat)] text-2xl leading-[1.15] text-app-blue">
            Better Decisions, Brighter Tomorrows.
          </p>
        </div>

        {/* Three principles */}
        <div className="mt-6 grid gap-6 border-t border-white/10 pt-14 sm:grid-cols-3 lg:mt-8">
          {principles.map((principle, index) => (
            <PrincipleCard key={principle.title} {...principle} index={index} />
          ))}
        </div>

        {/* Final marketing section */}
        <div className="relative mt-20 overflow-hidden rounded-3xl border border-white/10 lg:mt-24">
          <div className="red-atmosphere absolute inset-0" aria-hidden="true" />

          <div className="relative px-6 py-16 text-center sm:px-10 sm:py-20">
            <h3 className="mx-auto max-w-2xl font-[family-name:var(--font-display)] text-[clamp(2rem,5vw,3.25rem)] font-bold leading-[0.95] tracking-[-0.03em] text-app-text">
              DON&apos;T APPLY{" "}
              <span className="bg-gradient-to-r from-[#5cc6ff] via-[#8f7bff] to-[#b46bff] bg-clip-text text-transparent">
                BLIND.
              </span>
            </h3>

            <p className="mx-auto mt-4 max-w-md text-base leading-7 text-app-muted">
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

        {/* Foreground detail — bottom utility bar */}
        <div className="relative mt-14 flex flex-col items-center gap-5 border-t border-white/5 pt-6 text-center lg:flex-row lg:justify-between lg:text-left">
          <ProgressRail />

          <div className="flex flex-col items-center gap-2">
            <span className="mono text-[9px] tracking-[0.3em] text-app-muted">
              SCROLL TO CONTINUE
            </span>
            <Mouse className="h-4 w-4 text-app-muted" aria-hidden="true" />
            <ChevronDown
              className="scroll-dot -mt-1.5 h-3 w-3 text-app-muted"
              aria-hidden="true"
            />
          </div>

          <div className="mono text-[9px] leading-5 tracking-[0.2em] text-app-muted">
            SAME YOU.
            <br />
            A BRIGHTER TOMORROW.
          </div>
        </div>
      </div>
    </section>
  );
}

function InputPanel({
  icon: Icon,
  title,
  lines,
  index,
  parallaxX,
}: {
  icon: LucideIcon;
  title: string;
  lines: string[];
  index: number;
  parallaxX: number;
}) {
  return (
    <div
      data-reveal
      data-reveal-delay={index * 100}
      data-parallax-x={parallaxX}
      data-parallax-local
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
          <stop offset="55%" stopColor="#7a5cff" stopOpacity="0.55" />
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
      className="cine-focal relative flex h-52 w-52 shrink-0 items-center justify-center sm:h-56 sm:w-56"
    >
      <div
        className="job-intel-clarity-pulse absolute inset-0 rotate-45 rounded-[2.5rem] border border-app-blue/40 bg-gradient-to-br from-app-blue/10 via-transparent to-[#7a5cff]/15 backdrop-blur-sm"
        aria-hidden="true"
      />
      <div
        className="absolute inset-8 rotate-45 rounded-[1.75rem] border border-white/10"
        aria-hidden="true"
      />

      <p
        className="relative z-10 max-w-[150px] text-center font-[family-name:var(--font-display)] text-base font-semibold leading-tight text-app-text"
        role="img"
        aria-label="A clearer understanding — NERO's abstract representation of resolved job intelligence"
      >
        A Clearer
        <br />
        <span className="bg-gradient-to-r from-[#5cc6ff] to-[#b46bff] bg-clip-text text-transparent">
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
      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-app-border-soft text-app-blue">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </div>

      <h3 className="mt-4 text-sm font-semibold tracking-[0.15em] text-app-text">
        {title}
      </h3>

      <p className="mt-2 max-w-[280px] text-sm leading-6 text-app-muted">
        {text}
      </p>
    </div>
  );
}

function ProgressRail() {
  const activeIndex = PROGRESS_STEPS.indexOf(ACTIVE_STEP);
  const activePercent = (activeIndex / (PROGRESS_STEPS.length - 1)) * 100;

  return (
    <div className="flex flex-col items-center gap-2.5 lg:items-start" aria-hidden="true">
      <div className="relative h-px w-40 bg-app-border-soft">
        <span
          className="absolute -top-[3px] h-[7px] w-[7px] -translate-x-1/2 rounded-full bg-gradient-to-r from-app-blue to-[#8f5cff] shadow-[0_0_10px_rgba(143,92,255,0.7)]"
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
