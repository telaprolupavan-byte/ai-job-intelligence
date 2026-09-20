import Link from "next/link";
import {
  BarChart3,
  ChevronDown,
  FileCheck2,
  FileText,
  Lightbulb,
  Link2,
  Mouse,
  Search,
  User,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import NeroJobIntelligenceVisual from "@/components/app/nero-job-intelligence-visual";

const inputPanels: {
  icon: LucideIcon;
  title: string;
  lines: string[];
  iconClassName?: string;
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
    iconClassName: "text-[#b46bff]",
  },
  {
    icon: User,
    title: "Your Preferences",
    lines: ["Location", "Work Type", "Career Goals"],
  },
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

const PROGRESS_STEPS = ["01", "02", "03", "04", "05"];
const ACTIVE_INDEX = 3;

/**
 * Page 4 — "Know Before You Apply." (Job Intelligence).
 *
 * Same world as the hero/system sections above it: the same
 * background, technical grid, type scale, and micro-labels, just the
 * next scene in the scroll. The NERO/streams/crystal/environment
 * artwork is the approved reference image reproduced exactly (see
 * NeroJobIntelligenceVisual); everything else — panels, headline,
 * principles, CTA — stays real, accessible HTML positioned to match
 * it, so the page is still responsive and the CTA still works.
 */
export default function NeroJobIntelligenceSection() {
  return (
    <section
      id="job-intelligence"
      className="relative overflow-hidden border-t border-white/10 bg-[#0b0e14]"
    >
      {/* Layer 1 — background */}
      <div className="technical-grid absolute inset-0 opacity-30" aria-hidden="true" />
      <div className="job-intel-atmosphere absolute inset-0" aria-hidden="true" />

      <div className="relative mx-auto max-w-[1536px] px-6 py-12 sm:px-10 sm:py-14 lg:px-20 lg:py-16">
        {/* Foreground detail — top-right handwritten annotation */}
        <div
          className="pointer-events-none absolute right-6 top-10 z-20 hidden max-w-[180px] -rotate-2 text-right sm:right-10 lg:right-20 lg:block"
          aria-hidden="true"
        >
          <p className="font-[family-name:var(--font-caveat)] text-2xl leading-[1.15] text-[#bcdfff]">
            More
            <br />
            Clarity.
            <br />
            Brighter
            <br />
            Careers.
          </p>
          <span
            className="ml-auto mt-1 block h-0.5 w-16 -rotate-6 bg-gradient-to-r from-[#b46bff] to-app-blue"
            aria-hidden="true"
          />
        </div>

        {/* Header */}
        <div className="max-w-2xl">
          <div className="flex items-center gap-3">
            <span className="mono text-[10px] tracking-[0.3em]">
              <span className="text-[#b46bff]">04 / 05</span>{" "}
              <span className="text-app-body">JOB INTELLIGENCE</span>
            </span>
            <span className="h-px w-12 bg-white/15" />
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

        {/* Layer 2/3 — input panels + approved reference artwork */}
        <div className="job-intel-grid mt-8 lg:mt-9">
          <div className="job-intel-area-panels flex flex-col gap-4">
            {inputPanels.map((panel, index) => (
              <InputPanel key={panel.title} {...panel} index={index} />
            ))}
          </div>

          <div className="job-intel-area-scene flex items-center justify-center">
            <NeroJobIntelligenceVisual />
          </div>
        </div>

        {/* Three principles */}
        <div className="mt-6 grid gap-x-0 gap-y-10 sm:grid-cols-3 sm:divide-x sm:divide-white/10">
          {principles.map((principle, index) => (
            <PrincipleCard key={principle.title} {...principle} index={index} />
          ))}
        </div>

        {/* Final marketing section */}
        <div className="relative mt-8 py-4 text-center sm:mt-10">
          {/* Foreground detail — handwritten annotation beside the CTA */}
          <div
            className="pointer-events-none absolute left-0 top-1/2 hidden max-w-[190px] -translate-y-1/2 -rotate-2 text-left lg:block"
            aria-hidden="true"
          >
            <p className="font-[family-name:var(--font-caveat)] bg-gradient-to-b from-[#c77dff] to-[#5cc6ff] bg-clip-text text-2xl leading-[1.15] text-transparent">
              Better
              <br />
              Decisions
              <br />
              Brighter
              <br />
              Tomorrows.
            </p>
          </div>

          <span className="mono text-[10px] tracking-[0.3em] text-[#bcdfff]">
            IT&apos;S MORE THAN A JOB.
          </span>

          <h3 className="mx-auto mt-5 max-w-2xl font-[family-name:var(--font-display)] text-[clamp(2rem,5vw,3.25rem)] font-bold leading-[0.95] tracking-[-0.03em] text-app-text">
            DON&apos;T APPLY{" "}
            <span className="bg-gradient-to-r from-[#5cc6ff] via-[#8f7bff] to-[#b46bff] bg-clip-text text-transparent">
              BLIND.
            </span>
          </h3>

          <p className="mx-auto mt-4 max-w-md text-base leading-7 text-app-body">
            Understand first. Decide with confidence.
          </p>

          <Link
            href="/register"
            className="app-focus-ring group mt-8 inline-flex items-center justify-center gap-2 rounded-full bg-gradient-to-r from-app-blue to-[#8f5cff] px-6 py-3.5 text-sm font-medium text-white shadow-[0_0_28px_-4px_rgba(122,92,255,0.55)] transition hover:brightness-110"
          >
            See What NERO Can Do
            <span className="transition-transform group-hover:translate-x-1">
              →
            </span>
          </Link>
        </div>

        {/* Foreground detail — bottom utility bar */}
        <div className="relative mt-8 flex flex-col items-center gap-5 border-t border-white/5 pt-6 text-center lg:flex-row lg:justify-between lg:text-left">
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

          <div className="flex items-center gap-2.5">
            <span
              className="hidden h-px w-10 bg-gradient-to-r from-app-blue/60 to-transparent lg:block"
              aria-hidden="true"
            />
            <div className="mono text-[9px] leading-5 tracking-[0.2em] text-app-muted">
              SAME YOU.
              <br />
              A BRIGHTER
              <br />
              TOMORROW.
            </div>
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
  iconClassName,
}: {
  icon: LucideIcon;
  title: string;
  lines: string[];
  index: number;
  iconClassName?: string;
}) {
  return (
    <div
      className="system-card-reveal glass-panel relative rounded-2xl border border-app-border-soft p-4 shadow-[0_0_24px_-14px_rgba(10,132,255,0.5)]"
      style={{ animationDelay: `${index * 100}ms` }}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-app-blue/50 bg-app-surface/80",
            iconClassName ?? "text-app-blue",
          )}
        >
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
      className="system-card-reveal flex flex-col items-center px-6 text-center"
      style={{ animationDelay: `${index * 110}ms` }}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-app-blue/60 text-app-blue">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </div>

      <h3 className="mt-4 text-sm font-semibold tracking-[0.15em] text-app-text">
        {title}
      </h3>

      <p className="mt-2 max-w-[280px] text-sm leading-6 text-app-body">
        {text}
      </p>
    </div>
  );
}

function ProgressRail() {
  const activePercent = (ACTIVE_INDEX / (PROGRESS_STEPS.length - 1)) * 100;

  return (
    <div className="flex flex-col items-center gap-2.5 lg:items-start" aria-hidden="true">
      <div
        className="relative h-px w-40"
        style={{
          background: `linear-gradient(to right, #cbb6ff 0%, #cbb6ff ${activePercent}%, #2a3245 ${activePercent}%, #2a3245 100%)`,
        }}
      >
        <span
          className="absolute -top-[3px] h-[7px] w-[7px] -translate-x-1/2 rounded-full bg-gradient-to-r from-app-blue to-[#8f5cff] shadow-[0_0_10px_rgba(143,92,255,0.7)]"
          style={{ left: `${activePercent}%` }}
        />
      </div>

      <div className="flex items-center gap-3">
        {PROGRESS_STEPS.map((step, index) => (
          <span
            key={step}
            className={cn(
              "mono text-[10px] tracking-[0.1em]",
              index === ACTIVE_INDEX
                ? "font-bold text-app-text"
                : index < ACTIVE_INDEX
                  ? "text-app-text/80"
                  : "text-app-muted/50",
            )}
          >
            {step}
          </span>
        ))}
      </div>
    </div>
  );
}
