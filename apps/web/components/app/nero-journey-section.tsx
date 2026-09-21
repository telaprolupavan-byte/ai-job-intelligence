import type { CSSProperties } from "react";
import Image from "next/image";
import {
  BadgeCheck,
  Compass,
  FileText,
  Lightbulb,
  Search,
  Send,
  Sparkles,
  Target,
  type LucideIcon,
} from "lucide-react";
import SectionHeading from "@/components/app/section-heading";

const stages: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: FileText, title: "Resume", text: "Start with where you stand today." },
  { icon: Lightbulb, title: "Understand", text: "NERO reads your background and goals." },
  { icon: Search, title: "Discover", text: "Relevant opportunities surface." },
  { icon: Target, title: "Match", text: "See how well each one actually fits." },
  { icon: Sparkles, title: "Improve", text: "Strengthen what needs strengthening." },
  { icon: BadgeCheck, title: "Verify", text: "Recheck before you commit to anything." },
  { icon: Send, title: "Apply", text: "Submit with a clear picture, not a guess." },
  { icon: Compass, title: "Track", text: "Follow every application forward." },
];

/**
 * "The NERO Journey" — the throughline connecting Resume Intelligence
 * and Job Intelligence to the existing application-tracking scene
 * below it. Eight stages on a single vertical rail; each one activates
 * via the same IntersectionObserver-driven data-reveal used everywhere
 * else on the page, so the user visually progresses through the
 * journey exactly as fast as they scroll — no separate scroll-spy
 * logic, no per-frame state.
 *
 * STRONG storytelling tier: the rail's crimson->blue fill grows with
 * the section's own scroll transit, and the atmosphere carries two
 * independent depth layers. What it no longer does is drift each of
 * the eight stage icons at its own speed — the icons sit ON the rail
 * line, so giving each a different offset pulled them off the very
 * line that is the section's whole visual argument.
 *
 * Layout: a two-column shell on wide screens. The rail used to sit in
 * a 900px centered container with the NERO companion floating off its
 * right edge, which left the right half of a 1600px-tall section
 * completely empty. NERO now occupies a real second column.
 */
export default function NeroJourneySection() {
  return (
    <section
      id="nero-journey"
      className="relative overflow-hidden border-t border-white/10 bg-[#090c11]"
    >
      <div className="technical-grid absolute inset-0 opacity-25" aria-hidden="true" />
      <div
        data-parallax-speed="0.09"
        data-parallax-local
        className="journey-atmosphere-a absolute inset-0"
        aria-hidden="true"
      />
      <div
        data-parallax-speed="0.06"
        data-parallax-local
        className="journey-atmosphere-b absolute inset-0"
        aria-hidden="true"
      />

      <div className="landing-shell landing-shell-narrow landing-band">
        <SectionHeading
          align="center"
          eyebrow="THE NERO JOURNEY"
          title={
            <>
              ONE PATH.{" "}
              <span className="bg-gradient-to-r from-[#5cc6ff] via-[#8f7bff] to-[#b46bff] bg-clip-text text-transparent">
                EIGHT STEPS.
              </span>
            </>
          }
          lede="From your resume to a tracked application — the same system, the whole way."
          className="mx-auto max-w-2xl"
        />

        <div className="stack-xl grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,260px)] lg:items-center lg:gap-16">
          <div className="relative">
            {/* Rail line doubles as the section's literal "line
                progression": data-scroll-progress writes this element's
                own 0->1 viewport-transit progress to --scene-progress,
                which the nested .journey-rail-fill reads via CSS
                inheritance to grow a crimson->blue fill down from the
                top — "the path walked so far" — over the static line. */}
            <div
              data-scroll-progress
              className="pointer-events-none absolute bottom-3 left-6 top-3 w-px bg-gradient-to-b from-transparent via-app-border-strong to-transparent"
              aria-hidden="true"
            >
              <div className="journey-rail-fill absolute inset-x-0 top-0 h-full origin-top" />
            </div>

            <ol className="relative flex flex-col gap-8 sm:gap-9">
              {stages.map((stage, index) => (
                <li
                  key={stage.title}
                  data-reveal
                  data-reveal-delay={(index % 4) * 80}
                  style={{ "--reveal-distance": "18px" } as CSSProperties}
                  className="relative flex items-start gap-5 pl-16"
                >
                  <span className="absolute left-0 top-0 z-10 flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-app-blue/50 bg-app-bg text-app-blue shadow-[0_0_20px_-6px_rgba(10,132,255,0.5)]">
                    <stage.icon className="h-5 w-5" aria-hidden="true" />
                  </span>

                  <div className="min-w-0 pt-0.5">
                    <span className="mono text-[9px] tracking-[0.2em] text-app-faint">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <h3 className="mt-1 text-base font-semibold text-app-text">
                      {stage.title}
                    </h3>
                    <p className="mt-1 max-w-[420px] text-sm leading-6 text-app-muted">
                      {stage.text}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </div>

          {/* Mascot companion — same approved standing/pointing artwork
              reused across the page, walking the rail alongside the
              visitor rather than acting as a new character. On wide
              screens it sits centred against the full height of the
              rail rather than floating off its top-right corner. */}
          <div className="order-first lg:order-none">
            <div
              data-parallax-speed="0.06"
              data-parallax-scale-to="1.04"
              data-parallax-local
              className="pointer-events-none relative mx-auto w-[128px] sm:w-[150px] lg:mx-0 lg:w-full"
            >
              <div className="relative mx-auto hidden max-w-[190px] -rotate-2 rounded-2xl border border-app-border-soft bg-app-panel/85 px-4 py-2.5 shadow-lg backdrop-blur-sm lg:block">
                <p className="nero-note text-app-text">
                  I&apos;ll walk this with you.
                </p>
              </div>

              <Image
                src="/brand/nero-hero-figure.png"
                alt=""
                width={1098}
                height={1334}
                sizes="(min-width: 1024px) 260px, 150px"
                quality={95}
                className="nero-float relative z-10 mt-3 h-auto w-full drop-shadow-[0_20px_40px_rgba(0,0,0,0.5)]"
              />
              <div
                className="nero-floor-glow absolute -bottom-3 left-1/2 h-14 w-[85%] -translate-x-1/2"
                aria-hidden="true"
              />
            </div>
          </div>
        </div>

        <div data-reveal className="stack-lg flex justify-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-app-border-soft bg-app-panel/70 px-5 py-2.5">
            <span
              className="h-1.5 w-1.5 rounded-full bg-app-red shadow-[0_0_10px_rgba(255,59,48,0.6)]"
              aria-hidden="true"
            />
            <span className="mono text-center text-[10px] leading-5 tracking-[0.25em] text-app-text">
              YOU&apos;RE IN CONTROL, START TO FINISH
            </span>
          </span>
        </div>
      </div>
    </section>
  );
}
