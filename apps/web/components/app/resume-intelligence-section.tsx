import type { CSSProperties } from "react";
import Image from "next/image";
import {
  CheckCircle2,
  FileText,
  Lightbulb,
  RefreshCcw,
  ScanSearch,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import Badge from "@/components/app/badge";

const stages: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: FileText, title: "Resume", text: "Your resume, as it stands today." },
  { icon: ScanSearch, title: "Analyze", text: "NERO reviews it end to end." },
  { icon: Lightbulb, title: "Identify", text: "Gaps and weak spots surface." },
  { icon: Sparkles, title: "Improve", text: "Targeted suggestions, not rewrites." },
  { icon: RefreshCcw, title: "Recheck", text: "See the difference it made." },
];

const flaggedLines = [
  "Experience — needs stronger outcomes",
  "Skills — missing a few relevant tools",
  "Summary — could be more specific",
];

const improvedLines = [
  "Experience — outcomes made concrete",
  "Skills — relevant tools added",
  "Summary — tightened and specific",
];

/**
 * "Resume Intelligence" — the scene after the existing System section,
 * before Discover Jobs. A five-stage scroll sequence (Resume -> Analyze
 * -> Identify -> Improve -> Recheck) with a before/after resume mock
 * that reveals in two passes — flagged first, then resolved — so the
 * resume's own transition toward improvement is what communicates
 * progress, not a numeric score. No ATS percentage or score is
 * invented anywhere in this section.
 *
 * A small NERO cameo sits beside the header (same standing/pointing
 * artwork reused everywhere else) so the section's own companion
 * presence stays consistent with the rest of the page.
 */
export default function ResumeIntelligenceSection() {
  return (
    <section
      id="resume-intelligence"
      className="relative overflow-hidden border-t border-white/10 bg-[#0c0f16]"
    >
      <div className="technical-grid absolute inset-0 opacity-30" aria-hidden="true" />
      <div className="resume-intel-atmosphere absolute inset-0" aria-hidden="true" />

      <div className="relative mx-auto max-w-[1536px] px-6 py-16 sm:px-10 sm:py-20 lg:px-20 lg:py-28">
        <div className="flex flex-col gap-10 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <div className="flex items-center gap-3">
              <span className="mono text-[10px] tracking-[0.3em] text-app-red">
                RESUME INTELLIGENCE
              </span>
              <span className="h-px w-12 bg-app-red/50" />
            </div>

            <h2 className="mt-5 font-[family-name:var(--font-display)] text-[clamp(2.5rem,5.5vw,4rem)] font-extrabold leading-[0.95] tracking-[-0.03em] text-app-text">
              KNOW WHERE YOUR{" "}
              <span className="bg-gradient-to-r from-[#5cc6ff] via-[#8f7bff] to-[#b46bff] bg-clip-text text-transparent">
                RESUME
              </span>{" "}
              STANDS.
            </h2>

            <p className="mt-6 max-w-[540px] text-base leading-7 text-app-muted sm:text-lg">
              NERO reads your resume the way a hiring manager would, then
              shows you exactly what to strengthen before you apply.
            </p>
          </div>

          {/* Mascot cameo — same approved standing/pointing artwork used
              throughout the page, sized to sit beside the header on wide
              screens and centered below it on mobile, without taking
              over the section's existing before/after layout. */}
          <div className="relative mx-auto w-[130px] shrink-0 sm:mx-0 sm:w-[150px] lg:w-[170px]">
            <div className="pointer-events-none absolute -top-8 right-[-8%] z-20 hidden max-w-[170px] rotate-2 sm:block">
              <div className="relative rounded-2xl border border-app-border-soft bg-app-panel/85 px-4 py-3 shadow-lg backdrop-blur-sm">
                <p className="font-[family-name:var(--font-caveat)] text-xl leading-5 text-app-text">
                  Here&apos;s what I found.
                </p>
                <span
                  className="absolute -bottom-1.5 left-9 h-3.5 w-3.5 rotate-45 border-b border-r border-app-border-soft bg-app-panel/85"
                  aria-hidden="true"
                />
              </div>
            </div>

            <Image
              src="/brand/nero-hero-figure.png"
              alt="NERO, the AI Job Intelligence mascot, reviewing a resume"
              width={1098}
              height={1334}
              sizes="170px"
              quality={95}
              className="nero-float relative z-10 h-auto w-full drop-shadow-[0_20px_40px_rgba(0,0,0,0.5)]"
            />
            <div
              className="nero-floor-glow pointer-events-none absolute -bottom-3 left-1/2 h-14 w-[85%] -translate-x-1/2"
              aria-hidden="true"
            />
          </div>
        </div>

        {/* Stage rail */}
        <div className="relative mt-16 lg:mt-20">
          <div
            className="pointer-events-none absolute left-0 right-0 top-6 hidden h-px bg-gradient-to-r from-transparent via-app-border-strong to-transparent sm:block"
            aria-hidden="true"
          />
          <div className="grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-5 sm:gap-x-4">
            {stages.map((stage, index) => (
              <div
                key={stage.title}
                data-reveal
                data-reveal-delay={index * 110}
                className="relative flex flex-col items-center text-center"
              >
                <div className="relative z-10 flex h-12 w-12 items-center justify-center rounded-full border border-app-blue/50 bg-app-bg text-app-blue">
                  <stage.icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <h3 className="mt-3 text-sm font-semibold tracking-[0.1em] text-app-text">
                  {stage.title.toUpperCase()}
                </h3>
                <p className="mt-1.5 max-w-[140px] text-xs leading-5 text-app-muted">
                  {stage.text}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Before / after resume mock */}
        <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:mt-20 lg:gap-8">
          <div
            data-reveal
            style={{ "--reveal-distance": "18px" } as CSSProperties}
            className="glass-panel relative rounded-2xl border border-app-border-soft p-6 shadow-[0_0_24px_-16px_rgba(255,59,48,0.4)]"
          >
            <div className="flex items-center justify-between">
              <span className="mono text-[9px] tracking-[0.2em] text-app-faint">
                BEFORE
              </span>
              <Badge tone="red-soft">Needs attention</Badge>
            </div>
            <div className="mt-5 space-y-3">
              {flaggedLines.map((line) => (
                <p
                  key={line}
                  className="rounded-lg border border-app-red/20 bg-app-red-soft/40 px-3 py-2 text-xs leading-5 text-app-body"
                >
                  {line}
                </p>
              ))}
            </div>
          </div>

          <div
            data-reveal
            data-reveal-delay="220"
            style={{ "--reveal-distance": "18px" } as CSSProperties}
            className="glass-panel relative rounded-2xl border border-app-border-soft p-6 shadow-[0_0_24px_-16px_rgba(34,160,107,0.4)]"
          >
            <div className="flex items-center justify-between">
              <span className="mono text-[9px] tracking-[0.2em] text-app-faint">
                AFTER RECHECK
              </span>
              <Badge tone="success-soft">Strengthened</Badge>
            </div>
            <div className="mt-5 space-y-3">
              {improvedLines.map((line) => (
                <p
                  key={line}
                  className="flex items-start gap-2 rounded-lg border border-app-success/20 bg-app-success-soft/40 px-3 py-2 text-xs leading-5 text-app-body"
                >
                  <CheckCircle2
                    className="mt-0.5 h-3.5 w-3.5 shrink-0 text-app-success"
                    aria-hidden="true"
                  />
                  {line}
                </p>
              ))}
            </div>
          </div>
        </div>

        <p
          data-reveal
          data-reveal-delay="120"
          className="mx-auto mt-12 max-w-lg text-center font-[family-name:var(--font-caveat)] text-2xl leading-[1.2] text-app-blue sm:text-[26px]"
        >
          Real changes, not a score to chase.
        </p>
      </div>
    </section>
  );
}
