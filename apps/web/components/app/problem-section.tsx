import type { CSSProperties } from "react";
import Image from "next/image";
import { ArrowRight } from "lucide-react";
import SectionHeading from "@/components/app/section-heading";

const questions: { text: string; rotate: number }[] = [
  { text: "Is my resume ready?", rotate: -5 },
  { text: "Am I applying to the right jobs?", rotate: 3 },
  { text: "Does my experience actually match?", rotate: -2 },
  { text: "What should I change?", rotate: 4 },
  { text: "Am I making progress?", rotate: -4 },
];

/**
 * "The Problem" — the scene between Hero and Meet NERO.
 *
 * Same world as the rest of the page (technical-grid + atmosphere,
 * mono micro-labels, shared display/lede type steps), but every
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
 *
 * RESTRAINED motion tier. The chips previously each carried their own
 * data-parallax-speed, which meant that at any given scroll position
 * the five of them sat at five different vertical offsets — the
 * cluster read as a broken flex row rather than a settling cluster.
 * The drift now lives on one wrapper around the whole cluster, so the
 * chips keep their row alignment and only the tilt-to-flat settle
 * communicates "scattered questions resolving."
 */
export default function ProblemSection() {
  return (
    <section
      id="problem"
      className="relative overflow-hidden border-t border-white/10 bg-[#0a0d13]"
    >
      <div className="technical-grid absolute inset-0 opacity-20" aria-hidden="true" />
      {/* Whisper-subtle local parallax — LOW tier by design (contrast
          after the cinematic Hero), but every other section's
          atmosphere layer already drifts a hair on scroll; this keeps
          Problem from being the one flat exception. */}
      <div
        data-parallax-speed="0.03"
        data-parallax-local
        className="problem-atmosphere absolute inset-0"
        aria-hidden="true"
      />

      <div className="landing-shell landing-shell-narrow landing-band">
        <SectionHeading
          align="center"
          eyebrow="THE PROBLEM"
          title={
            <>
              Job searching shouldn&apos;t feel like{" "}
              <span className="text-app-muted">guesswork.</span>
            </>
          }
          titleClassName="leading-[1.14]"
          className="mx-auto max-w-3xl"
        />

        <div
          data-parallax-speed="0.035"
          data-parallax-local
          className="stack-lg mx-auto flex max-w-[920px] flex-wrap items-center justify-center gap-2.5 sm:gap-3.5"
        >
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
              className="glass-panel block rounded-full border border-app-border-soft px-5 py-2.5 text-sm text-app-body sm:text-base"
            >
              {question.text}
            </span>
          ))}
        </div>

        {/* Resolution line — the section's single focal moment. Laid
            out as one centered row (arrow -> statement -> NERO) rather
            than a right-aligned block floating under a centered
            header, which is what made the old composition read as two
            unrelated alignments stacked on top of each other. */}
        <div className="stack-lg flex flex-col items-center gap-6 sm:flex-row sm:justify-center sm:gap-7">
          <div
            data-reveal
            data-reveal-delay="460"
            style={{ "--reveal-distance": "10px" } as CSSProperties}
            className="flex items-center gap-4 text-center sm:text-right"
          >
            <ArrowRight
              className="hidden h-5 w-5 shrink-0 text-app-red/70 sm:block"
              aria-hidden="true"
            />
            <p className="display-sub max-w-[420px]">
              NERO turns those questions into{" "}
              <span className="bg-gradient-to-r from-[#5cc6ff] to-app-blue bg-clip-text text-transparent">
                intelligence.
              </span>
            </p>
          </div>

          <div
            data-parallax-speed="0.07"
            data-parallax-local
            className="relative w-32 shrink-0 sm:w-40 lg:w-48"
          >
            <div
              data-reveal
              data-reveal-delay="540"
              style={{ "--reveal-distance": "14px" } as CSSProperties}
              className="relative"
            >
              {/* Attention / empathetic beat: he arrives at the end of a
                  run of anxious questions, so he is bigger than he was
                  (he was the smallest figure on the page, which read as
                  a sticker rather than someone stepping in) but moves
                  the least — a slow, shallow hover, 7.4s / 9px against
                  the 6s / 14px default. Listening, not performing. */}
              <Image
                src="/brand/nero-hero-figure.png"
                alt="NERO, the AI Job Intelligence mascot, arriving to make sense of the questions above"
                width={1098}
                height={1334}
                sizes="190px"
                quality={95}
                style={
                  {
                    "--nero-float-duration": "7.4s",
                    "--nero-float-distance": "9px",
                  } as CSSProperties
                }
                className="nero-float relative z-10 h-auto w-full drop-shadow-[0_20px_40px_rgba(0,0,0,0.5)]"
              />
              <div
                className="nero-floor-glow pointer-events-none absolute -bottom-3 left-1/2 h-12 w-[85%] -translate-x-1/2"
                aria-hidden="true"
              />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
