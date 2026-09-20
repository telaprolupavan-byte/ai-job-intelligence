import Image from "next/image";
import { FileCheck2, Search, Send, type LucideIcon } from "lucide-react";

const pillars: { icon: LucideIcon; title: string; text: string }[] = [
  {
    icon: FileCheck2,
    title: "Resume Intelligence",
    text: "Understand where your resume stands and what to strengthen.",
  },
  {
    icon: Search,
    title: "Job Intelligence",
    text: "See how a specific opportunity actually lines up with you.",
  },
  {
    icon: Send,
    title: "Application Intelligence",
    text: "Know where every application stands, at every stage.",
  },
];

/**
 * "Meet NERO" — the scene between The Problem and the existing System
 * section. Introduces the character and the three intelligence
 * pillars the rest of the page walks through in detail (Resume
 * Intelligence, Job Intelligence, the application journey) before the
 * existing System section elaborates the underlying four-step
 * workflow. Reuses the approved standing/pointing NERO artwork — no
 * new pose, no chat affordance; NERO stays the visual anchor, not an
 * interactive agent.
 */
export default function MeetNeroSection() {
  return (
    <section
      id="meet-nero"
      className="relative overflow-hidden border-t border-white/10 bg-[#0b0e14]"
    >
      <div className="technical-grid absolute inset-0 opacity-30" aria-hidden="true" />
      <div
        data-parallax-speed="0.07"
        data-parallax-local
        className="meet-nero-atmosphere-blue absolute inset-0"
        aria-hidden="true"
      />
      <div
        data-parallax-speed="0.05"
        data-parallax-local
        className="meet-nero-atmosphere-red absolute inset-0"
        aria-hidden="true"
      />

      <div className="relative mx-auto max-w-[1536px] px-6 py-20 sm:px-10 sm:py-24 lg:px-20 lg:py-28">
        <div className="grid gap-14 lg:grid-cols-[1fr_minmax(0,440px)] lg:items-center lg:gap-16">
          <div>
            <div className="flex items-center gap-3">
              <span className="mono text-[10px] tracking-[0.3em] text-app-red">
                MEET NERO
              </span>
              <span className="h-px w-12 bg-app-red/50" />
            </div>

            <h2 className="mt-5 font-[family-name:var(--font-display)] text-[clamp(2.5rem,5.5vw,4rem)] font-extrabold leading-[0.95] tracking-[-0.03em] text-app-text">
              MEET{" "}
              <span className="bg-gradient-to-r from-[#8fdcff] via-[#5cc6ff] to-app-blue bg-clip-text text-transparent">
                NERO.
              </span>
            </h2>

            <p className="mt-6 max-w-[520px] text-base leading-7 text-app-muted sm:text-lg">
              NERO is your AI job intelligence companion — built to help
              you understand your position, your opportunities, and your
              next move.
            </p>

            <div className="mt-12 grid gap-5 sm:grid-cols-3 lg:grid-cols-1">
              {pillars.map((pillar, index) => (
                <div
                  key={pillar.title}
                  data-reveal
                  data-reveal-delay={index * 100}
                  className="flex items-start gap-3.5 rounded-xl border border-app-border-soft bg-app-panel/50 p-4"
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-app-blue/50 bg-app-surface/80 text-app-blue">
                    <pillar.icon className="h-4 w-4" aria-hidden="true" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-app-text">
                      {pillar.title}
                    </h3>
                    <p className="mt-1 text-xs leading-5 text-app-muted">
                      {pillar.text}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div
            data-parallax-speed="0.1"
            data-parallax-local
            className="relative mx-auto w-full max-w-[360px] lg:max-w-none"
          >
            <Image
              src="/brand/nero-hero-figure.png"
              alt="NERO, the AI Job Intelligence mascot"
              width={1098}
              height={1334}
              sizes="(min-width: 1024px) 400px, (min-width: 640px) 340px, 260px"
              quality={95}
              className="nero-float relative z-10 h-auto w-full drop-shadow-[0_30px_60px_rgba(0,0,0,0.55)]"
            />
            <div
              className="nero-floor-glow pointer-events-none absolute -bottom-4 left-1/2 h-24 w-[85%] -translate-x-1/2"
              aria-hidden="true"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
