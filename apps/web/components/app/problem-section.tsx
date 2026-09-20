import type { CSSProperties } from "react";
import Image from "next/image";
import { ArrowDown } from "lucide-react";

const questions: { text: string; rotate: number }[] = [
  { text: "Is my resume ready?", rotate: -6 },
  { text: "Am I applying to the right jobs?", rotate: 4 },
  { text: "Does my experience actually match?", rotate: -3 },
  { text: "What should I change?", rotate: 5 },
  { text: "Am I making progress?", rotate: -5 },
];

/**
 * "The Problem" — the scene between Hero and Meet NERO.
 *
 * Same world as the rest of the page (technical-grid + atmosphere,
 * mono micro-labels, system-card-reveal-era typography), but every
 * question chip starts at its own tilt and un-rotates to flat as it's
 * scrolled into view (data-reveal's --reveal-rotate), so the cluster
 * visually settles from scattered guesswork into a single clear line
 * — "NERO turns those questions into intelligence" — without any
 * continuous per-frame animation.
 *
 * NERO itself arrives at that resolution line — the same approved
 * standing/pointing artwork reused everywhere else on the page, kept
 * small and quieter than its later full-scale appearances so the
 * section's dimmer mood still reads as "guesswork resolving," not a
 * bright hero entrance.
 */
export default function ProblemSection() {
  return (
    <section
      id="problem"
      className="relative overflow-hidden border-t border-white/10 bg-[#0a0d13]"
    >
      <div className="technical-grid absolute inset-0 opacity-20" aria-hidden="true" />
      <div className="problem-atmosphere absolute inset-0" aria-hidden="true" />

      <div className="relative mx-auto max-w-[1100px] px-6 py-20 sm:px-10 sm:py-24 lg:px-20 lg:py-28">
        <div className="flex flex-col items-center text-center">
          <div className="flex items-center gap-3">
            <span className="h-px w-10 bg-app-red/50" />
            <span className="mono text-[10px] tracking-[0.3em] text-app-red">
              THE PROBLEM
            </span>
            <span className="h-px w-10 bg-app-red/50" />
          </div>

          <h2 className="mt-6 max-w-2xl font-[family-name:var(--font-display)] text-[clamp(2rem,4.5vw,3.25rem)] font-bold leading-[1.05] tracking-[-0.02em] text-app-text">
            Job searching shouldn&apos;t feel like{" "}
            <span className="text-app-muted">guesswork.</span>
          </h2>
        </div>

        <div className="mt-16 flex flex-wrap items-center justify-center gap-3 sm:mt-20 sm:gap-4">
          {questions.map((question, index) => (
            <span
              key={question.text}
              data-reveal
              data-reveal-delay={index * 90}
              style={
                {
                  "--reveal-distance": "14px",
                  "--reveal-rotate": `${question.rotate}deg`,
                } as CSSProperties
              }
              className="glass-panel rounded-full border border-app-border-soft px-5 py-2.5 text-sm text-app-body sm:text-base"
            >
              {question.text}
            </span>
          ))}
        </div>

        <div className="mx-auto mt-16 flex max-w-2xl flex-col items-center gap-6 sm:mt-20 lg:flex-row lg:justify-center lg:gap-8">
          <div
            data-reveal
            data-reveal-delay="480"
            style={{ "--reveal-distance": "10px" } as CSSProperties}
            className="flex max-w-md flex-col items-center gap-4 text-center lg:items-end lg:text-right"
          >
            <ArrowDown className="h-5 w-5 text-app-muted" aria-hidden="true" />
            <p className="font-[family-name:var(--font-display)] text-xl font-semibold tracking-[-0.01em] text-app-text sm:text-2xl">
              NERO turns those questions into{" "}
              <span className="bg-gradient-to-r from-[#5cc6ff] to-app-blue bg-clip-text text-transparent">
                intelligence.
              </span>
            </p>
          </div>

          <div
            data-reveal
            data-reveal-delay="560"
            style={{ "--reveal-distance": "14px" } as CSSProperties}
            className="relative w-28 shrink-0 opacity-90 sm:w-32"
          >
            <Image
              src="/brand/nero-hero-figure.png"
              alt="NERO, the AI Job Intelligence mascot, arriving to make sense of the questions above"
              width={1098}
              height={1334}
              sizes="130px"
              quality={95}
              className="nero-float relative z-10 h-auto w-full drop-shadow-[0_20px_40px_rgba(0,0,0,0.5)]"
            />
            <div
              className="nero-floor-glow pointer-events-none absolute -bottom-3 left-1/2 h-12 w-[85%] -translate-x-1/2"
              aria-hidden="true"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
