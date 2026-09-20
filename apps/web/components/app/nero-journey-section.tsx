import type { CSSProperties } from "react";
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
 * logic, no per-frame state. The strongest parallax section on the
 * page: the rail's background glow and connecting line carry their
 * own depth layers, and each stage's icon drifts a hair independently
 * of its text for a subtle layered feel without ever competing with
 * legibility.
 */
export default function NeroJourneySection() {
  return (
    <section
      id="nero-journey"
      className="relative overflow-hidden border-t border-white/10 bg-[#090c11]"
    >
      <div className="technical-grid absolute inset-0 opacity-25" aria-hidden="true" />
      <div
        data-parallax-speed="0.05"
        data-parallax-local
        className="journey-atmosphere-a absolute inset-0"
        aria-hidden="true"
      />
      <div
        data-parallax-speed="0.03"
        data-parallax-local
        className="journey-atmosphere-b absolute inset-0"
        aria-hidden="true"
      />

      <div className="relative mx-auto max-w-[900px] px-6 py-20 sm:px-10 sm:py-24 lg:px-20 lg:py-28">
        <div className="text-center">
          <div className="flex items-center justify-center gap-3">
            <span className="h-px w-10 bg-app-red/50" />
            <span className="mono text-[10px] tracking-[0.3em] text-app-red">
              THE NERO JOURNEY
            </span>
            <span className="h-px w-10 bg-app-red/50" />
          </div>

          <h2 className="mx-auto mt-5 max-w-lg font-[family-name:var(--font-display)] text-[clamp(2.25rem,5vw,3.5rem)] font-extrabold leading-[0.95] tracking-[-0.03em] text-app-text">
            ONE PATH.{" "}
            <span className="bg-gradient-to-r from-[#5cc6ff] via-[#8f7bff] to-[#b46bff] bg-clip-text text-transparent">
              EIGHT STEPS.
            </span>
          </h2>

          <p className="mx-auto mt-5 max-w-md text-base leading-7 text-app-muted">
            From your resume to a tracked application — the same
            system, the whole way.
          </p>
        </div>

        <div className="relative mt-16 lg:mt-20">
          <div
            data-parallax-speed="0.04"
            data-parallax-local
            className="pointer-events-none absolute left-6 top-2 bottom-2 w-px bg-gradient-to-b from-transparent via-app-border-strong to-transparent"
            aria-hidden="true"
          />

          <ol className="relative flex flex-col gap-10 sm:gap-12">
            {stages.map((stage, index) => (
              <li
                key={stage.title}
                data-reveal
                data-reveal-delay={(index % 4) * 90}
                style={{ "--reveal-distance": "20px" } as CSSProperties}
                className="relative flex items-start gap-5 pl-16"
              >
                <span
                  data-parallax-speed={(0.01 + index * 0.006).toFixed(3)}
                  data-parallax-local
                  className="absolute left-0 z-10 flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-app-blue/50 bg-app-bg text-app-blue shadow-[0_0_20px_-6px_rgba(10,132,255,0.5)]"
                >
                  <stage.icon className="h-5 w-5" aria-hidden="true" />
                </span>

                <div className="min-w-0">
                  <span className="mono text-[9px] tracking-[0.2em] text-app-faint">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <h3 className="mt-1 text-lg font-semibold text-app-text">
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

        <div
          data-reveal
          className="mx-auto mt-16 flex max-w-md justify-center lg:mt-20"
        >
          <span className="inline-flex items-center gap-2 rounded-full border border-app-border-soft bg-app-panel/70 px-5 py-2.5">
            <span
              className="h-1.5 w-1.5 rounded-full bg-app-red shadow-[0_0_10px_rgba(255,59,48,0.6)]"
              aria-hidden="true"
            />
            <span className="mono text-[10px] tracking-[0.25em] text-app-text">
              YOU&apos;RE IN CONTROL, START TO FINISH
            </span>
          </span>
        </div>
      </div>
    </section>
  );
}
