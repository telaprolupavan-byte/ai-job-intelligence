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
import SectionHeading from "@/components/app/section-heading";

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
 *
 * STRONG motion tier — but the strength now lives in the scan line and
 * the "after" card filling in, not in per-element drift. The five rail
 * icons and the two mock cards each used to carry their own
 * data-parallax-speed, which meant a row that is supposed to be a
 * single horizontal sequence stair-stepped downward by ~25px across
 * its five items, and the before/after pair never shared a top edge.
 * Both now drift as one group.
 */
export default function ResumeIntelligenceSection() {
  return (
    <section
      id="resume-intelligence"
      className="relative overflow-hidden border-t border-white/10 bg-[#0c0f16]"
    >
      <div className="technical-grid absolute inset-0 opacity-30" aria-hidden="true" />
      <div
        data-parallax-speed="0.08"
        data-parallax-local
        className="resume-intel-atmosphere absolute inset-0"
        aria-hidden="true"
      />

      <div className="landing-shell landing-band">
        <div className="flex flex-col gap-10 lg:flex-row lg:items-center lg:justify-between lg:gap-12">
          <SectionHeading
            eyebrow="RESUME INTELLIGENCE"
            title={
              <>
                KNOW WHERE YOUR{" "}
                <span className="bg-gradient-to-r from-[#5cc6ff] via-[#8f7bff] to-[#b46bff] bg-clip-text text-transparent">
                  RESUME
                </span>{" "}
                STANDS.
              </>
            }
            lede="NERO reads your resume the way a hiring manager would, then shows you exactly what to strengthen before you apply."
            className="max-w-2xl"
          />

          {/* Mascot cameo — same approved standing/pointing artwork used
              throughout the page, sized to sit beside the header on wide
              screens and centered below it on mobile, without taking
              over the section's existing before/after layout. A gentle
              scroll-linked scale-up reads as NERO leaning in to analyze,
              STRONG-tier per the cinematic-pass motion map. */}
          <div
            data-parallax-speed="0.08"
            data-parallax-scale-to="1.05"
            data-parallax-local
            className="relative mx-auto w-[150px] shrink-0 sm:w-[170px] lg:mx-0 lg:mr-6 lg:w-[190px]"
          >
            <div className="pointer-events-none absolute left-1/2 top-2 z-20 w-[168px] -translate-x-1/2 rotate-2 sm:left-auto sm:right-[74%] sm:top-6 sm:translate-x-0">
              <div className="relative rounded-2xl border border-app-border-soft bg-app-panel/85 px-4 py-2.5 shadow-lg backdrop-blur-sm">
                <p className="nero-note text-app-text">
                  Here&apos;s what I found.
                </p>
                <span
                  className="absolute -bottom-1.5 left-9 h-3.5 w-3.5 rotate-45 border-b border-r border-app-border-soft bg-app-panel/85 sm:-right-1.5 sm:bottom-auto sm:left-auto sm:top-6 sm:-rotate-45"
                  aria-hidden="true"
                />
              </div>
            </div>

            <Image
              src="/brand/nero-hero-figure.png"
              alt="NERO, the AI Job Intelligence mascot, reviewing a resume"
              width={1098}
              height={1334}
              sizes="190px"
              quality={95}
              className="nero-float relative z-10 h-auto w-full drop-shadow-[0_20px_40px_rgba(0,0,0,0.5)]"
            />
            <div
              className="nero-floor-glow pointer-events-none absolute -bottom-3 left-1/2 h-14 w-[85%] -translate-x-1/2"
              aria-hidden="true"
            />
          </div>
        </div>

        {/* Stage rail — one drift wrapper for the whole sequence so the
            five icons stay on the same baseline and the hairline that
            joins them stays a straight line. */}
        <div
          data-parallax-speed="0.03"
          data-parallax-local
          className="stack-xl relative"
        >
          <div
            className="pointer-events-none absolute left-[10%] right-[10%] top-6 hidden h-px bg-gradient-to-r from-transparent via-app-border-strong to-transparent sm:block"
            aria-hidden="true"
          />
          <div className="grid grid-cols-2 gap-x-6 gap-y-9 sm:grid-cols-5 sm:gap-x-4">
            {stages.map((stage, index) => (
              <div
                key={stage.title}
                data-reveal
                data-reveal-delay={index * 110}
                style={{ "--reveal-distance": "14px" } as CSSProperties}
                className="relative flex flex-col items-center text-center"
              >
                <div className="relative z-10 flex h-12 w-12 items-center justify-center rounded-full border border-app-blue/50 bg-app-bg text-app-blue">
                  <stage.icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <h3 className="mt-3.5 text-xs font-semibold tracking-[0.18em] text-app-text">
                  {stage.title.toUpperCase()}
                </h3>
                <p className="mt-1.5 max-w-[150px] text-xs leading-5 text-app-muted">
                  {stage.text}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Before / after resume mock. data-reveal uses a plain CSS
            transition (not a @keyframes ...forwards animation), so —
            unlike reveal-up/nero-float elsewhere on the page — it's
            safe to combine directly with data-parallax-speed on the
            same element: a transition just interpolates computed-value
            changes rather than locking out inline-style updates for the
            property, so the JS parallax write and the reveal's
            opacity/transform settle coexist. data-scroll-progress only
            ever writes the --scene-progress custom property, never
            transform, so it never has this conflict at all.

            The pair shares a single parallax wrapper: two side-by-side
            cards that are meant to be read against each other have to
            keep the same top edge, and giving each its own speed put
            them ~14px out of register at every scroll position. */}
        <div
          data-parallax-speed="0.04"
          data-parallax-local
          className="stack-xl grid grid-cols-1 items-stretch gap-5 sm:grid-cols-2 lg:gap-6"
        >
          <div
            data-reveal
            data-scroll-progress
            style={{ "--reveal-distance": "18px" } as CSSProperties}
            className="glass-panel relative flex flex-col overflow-hidden rounded-2xl border border-app-border-soft p-6 shadow-[0_0_24px_-16px_rgba(255,59,48,0.4)]"
          >
            {/* Reads as NERO actively scanning the resume — a thin
                line traveling down the card, tied to this panel's own
                scroll transit rather than a fixed-duration loop. */}
            <div className="resume-scan-line" aria-hidden="true" />
            <div className="flex items-center justify-between gap-3">
              <span className="mono text-[9px] tracking-[0.2em] text-app-faint">
                BEFORE
              </span>
              <Badge tone="red-soft">Needs attention</Badge>
            </div>
            <div className="mt-5 space-y-3">
              {flaggedLines.map((line) => (
                <p
                  key={line}
                  className="rounded-lg border border-app-red/20 bg-app-red-soft/40 px-3 py-2.5 text-xs leading-5 text-app-body"
                >
                  {line}
                </p>
              ))}
            </div>
          </div>

          <div
            data-reveal
            data-reveal-delay="180"
            style={{ "--reveal-distance": "18px" } as CSSProperties}
            className="glass-panel relative flex flex-col rounded-2xl border border-app-border-soft p-6 shadow-[0_0_24px_-16px_rgba(34,160,107,0.4)]"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="mono text-[9px] tracking-[0.2em] text-app-faint">
                AFTER RECHECK
              </span>
              <Badge tone="success-soft">Strengthened</Badge>
            </div>
            {/* Staged reveal — the resolved lines sweep into view top
                to bottom as this card transits the viewport, reading
                as the resume being rewritten rather than the two
                cards simply trading places. */}
            <div
              data-scroll-progress
              className="resume-recheck-reveal mt-5 space-y-3"
            >
              {improvedLines.map((line) => (
                <p
                  key={line}
                  className="flex items-start gap-2 rounded-lg border border-app-success/20 bg-app-success-soft/40 px-3 py-2.5 text-xs leading-5 text-app-body"
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
          className="nero-note stack-lg mx-auto max-w-lg text-center text-app-blue"
        >
          Real changes, not a score to chase.
        </p>
      </div>
    </section>
  );
}
