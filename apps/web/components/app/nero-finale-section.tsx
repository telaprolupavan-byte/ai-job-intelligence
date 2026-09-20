import type { CSSProperties } from "react";
import Link from "next/link";
import NeroFinaleVisual from "@/components/app/nero-finale-visual";

/**
 * "Same You. A Brighter Tomorrow." — the page's cinematic finale and
 * final conversion moment, and the last section before the footer.
 * Extracted into its own file (previously lived alongside the removed
 * "Make Your Next Move" section) — content unchanged.
 *
 * Depth pass: this scene previously had no entrance motion at all
 * (every other scene reveals via data-reveal). Eyebrow -> headline ->
 * subtext -> CTA now stage in with increasing delay so the CTA is
 * the last thing to fully arrive — the intended "final focal point"
 * — rather than everything appearing at once with the section.
 */
export default function NeroFinaleSection() {
  return (
    <section
      id="pricing"
      className="relative overflow-hidden border-t border-white/10 bg-[#0a0d13]"
    >
      <div className="relative mx-auto max-w-[1536px] px-6 py-16 sm:px-10 sm:py-20 lg:px-20 lg:py-28">
        <div className="relative scroll-mt-24 overflow-hidden rounded-3xl border border-white/10">
          <NeroFinaleVisual />

          <div
            data-parallax-speed="0.05"
            data-parallax-local
            className="pointer-events-none absolute left-5 top-6 z-20 max-w-[170px] -rotate-2 sm:left-8 sm:top-8"
            aria-hidden="true"
          >
            <p className="font-[family-name:var(--font-caveat)] text-xl leading-[1.15] text-app-text/90 sm:text-2xl">
              Same You.
              <br />
              Higher Possibilities.
            </p>
          </div>

          <div
            data-parallax-speed="0.05"
            data-parallax-local
            className="pointer-events-none absolute right-5 top-6 z-20 hidden max-w-[190px] rotate-2 text-right sm:right-8 sm:top-8 sm:block"
            aria-hidden="true"
          >
            <p className="font-[family-name:var(--font-caveat)] text-xl leading-[1.15] text-app-text/90 sm:text-2xl">
              More Opportunities.
              <br />
              A Brighter You.
            </p>
          </div>

          <div className="relative z-10 flex flex-col items-center px-6 pt-20 pb-64 text-center sm:px-10 sm:pt-24 sm:pb-80 lg:py-28 lg:pl-64">
            <div
              data-reveal
              className="flex items-center gap-3"
            >
              <span className="hidden h-px w-10 bg-app-red/50 sm:block" aria-hidden="true" />
              <span className="mono text-[10px] tracking-[0.3em] text-app-red">
                05 / 06 &nbsp; IT&apos;S MORE THAN A JOB.
              </span>
              <span className="hidden h-px w-10 bg-app-red/50 sm:block" aria-hidden="true" />
            </div>

            {/* data-reveal is a plain CSS transition (not a
                @keyframes ...forwards animation), so it's safe to
                combine directly with data-parallax-speed on the same
                element — a transition just interpolates computed-value
                changes rather than locking out inline-style updates,
                unlike reveal-up/nero-float/system-card-reveal elsewhere
                on the page (which do need the wrapper split). */}
            <h2
              data-reveal
              data-reveal-delay="120"
              data-parallax-speed="0.03"
              data-parallax-local
              style={{ "--reveal-distance": "22px" } as CSSProperties}
              className="mt-6 font-[family-name:var(--font-display)] text-[clamp(2.75rem,7vw,5.5rem)] font-bold leading-[1.1] tracking-[-0.03em] text-app-text"
            >
              SAME YOU.
              <br />
              <span className="bg-gradient-to-r from-app-red via-[#ff6a52] to-[#ff9166] bg-clip-text text-transparent">
                A BRIGHTER TOMORROW.
              </span>
            </h2>

            <p
              data-reveal
              data-reveal-delay="260"
              className="mx-auto mt-6 max-w-xl text-base leading-7 text-app-muted sm:text-lg"
            >
              Start your next chapter with NERO.
            </p>

            {/* The scene's closing focal point — staged in last, and
                with the biggest rise distance, so it arrives with the
                most visual weight of anything in the finale. */}
            <div
              data-reveal
              data-reveal-delay="420"
              style={{ "--reveal-distance": "30px" } as CSSProperties}
              className="mt-9 flex flex-col items-center gap-3 sm:flex-row"
            >
              <Link
                href="/register"
                className="app-focus-ring group inline-flex items-center justify-center gap-2 rounded-lg bg-crimson-fill px-7 py-3.5 text-sm font-medium text-white shadow-[0_0_28px_rgba(217,40,31,0.4)] transition hover:bg-crimson-fill-hover"
              >
                Get Started
                <span className="transition-transform group-hover:translate-x-1">
                  →
                </span>
              </Link>

              <Link
                href="/jobs"
                className="app-focus-ring inline-flex items-center justify-center rounded-lg border border-app-border-soft bg-black/20 px-7 py-3.5 text-sm font-medium text-app-text backdrop-blur-sm transition hover:bg-white/10"
              >
                Explore NERO
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
