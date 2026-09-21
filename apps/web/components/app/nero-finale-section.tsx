import type { CSSProperties } from "react";
import Link from "next/link";
import NeroFinaleVisual from "@/components/app/nero-finale-visual";

/**
 * "Same You. A Brighter Tomorrow." — the page's cinematic finale and
 * final conversion moment, and the last section before the footer.
 *
 * STRONGEST closing tier: eyebrow -> headline -> subtext -> CTA stage
 * in with increasing delay so the CTA is the last thing to fully
 * arrive, over a layered parallax environment (sky, horizon, ridges,
 * skyline, NERO) that recedes behind it.
 *
 * Polish pass fixes:
 *  - The scene block carried pb-64 / sm:pb-80 to leave room for the
 *    absolutely positioned NERO. That is 256-320px of empty card under
 *    the CTA on every phone. The figure is now part of the flow at
 *    those widths and the padding is gone.
 *  - The CTA row used to sit directly on top of the SVG skyline, with
 *    lit building windows showing through between the two buttons. It
 *    now has its own scrim.
 *  - The desktop content block was pushed right by a flat pl-64 while
 *    the card's own centre stayed put, so nothing in the scene shared
 *    a centre line. The card is now a real two-zone grid.
 */
export default function NeroFinaleSection() {
  return (
    <section
      id="pricing"
      className="relative overflow-hidden border-t border-white/10 bg-[#0a0d13]"
    >
      <div className="landing-shell landing-band">
        <div className="relative scroll-mt-24 overflow-hidden rounded-3xl border border-white/10">
          <NeroFinaleVisual />

          <div
            data-parallax-speed="0.05"
            data-parallax-local
            className="pointer-events-none absolute left-5 top-6 z-20 max-w-[170px] -rotate-2 sm:left-8 sm:top-8"
            aria-hidden="true"
          >
            <p className="nero-note text-app-text/90">
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
            <p className="nero-note text-app-text/90">
              More Opportunities.
              <br />
              A Brighter You.
            </p>
          </div>

          <div className="finale-stage relative z-10">
            {/* NERO's zone. On mobile it is a real flow row under the
                copy; from lg up it becomes the left half of the stage
                and the figure inside NeroFinaleVisual takes over. */}
            <div className="finale-stage-figure" aria-hidden="true" />

            <div className="finale-stage-copy flex flex-col items-center px-6 pb-14 pt-28 text-center sm:px-10 sm:pt-32 lg:px-4 lg:py-28">
              <div data-reveal className="flex items-center gap-3">
                <span
                  className="hidden h-px w-10 bg-app-red/50 sm:block"
                  aria-hidden="true"
                />
                <span className="mono text-[10px] tracking-[0.3em] text-app-red">
                  05 / 06 &nbsp; IT&apos;S MORE THAN A JOB.
                </span>
                <span
                  className="hidden h-px w-10 bg-app-red/50 sm:block"
                  aria-hidden="true"
                />
              </div>

              {/* data-reveal is a plain CSS transition (not a
                  @keyframes ...forwards animation), so it's safe to
                  combine directly with data-parallax-speed on the same
                  element — a transition just interpolates computed-value
                  changes rather than locking out inline-style updates,
                  unlike reveal-up/nero-float elsewhere on the page
                  (which do need the wrapper split). */}
              <h2
                data-reveal
                data-reveal-delay="120"
                data-parallax-speed="0.03"
                data-parallax-local
                style={{ "--reveal-distance": "22px" } as CSSProperties}
                className="finale-headline mt-6"
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
                className="section-lede mx-auto mt-5 text-center"
              >
                Start your next chapter with NERO.
              </p>

              {/* The scene's closing focal point — staged in last, and
                  with the biggest rise distance, so it arrives with the
                  most visual weight of anything in the finale. The
                  scrim behind it keeps the buttons legible over the
                  skyline they sit on. */}
              <div
                data-reveal
                data-reveal-delay="420"
                style={{ "--reveal-distance": "30px" } as CSSProperties}
                className="finale-cta relative mt-8 flex flex-col items-center gap-3 rounded-2xl px-6 py-5 sm:flex-row"
              >
                <Link
                  href="/register"
                  className="app-focus-ring group inline-flex items-center justify-center gap-2 rounded-lg bg-crimson-fill px-7 py-3.5 text-sm font-medium text-white shadow-[0_0_28px_rgba(217,40,31,0.45)] transition hover:bg-crimson-fill-hover"
                >
                  Get Started
                  <span className="transition-transform group-hover:translate-x-1">
                    →
                  </span>
                </Link>

                <Link
                  href="/jobs"
                  className="app-focus-ring inline-flex items-center justify-center rounded-lg border border-white/20 bg-black/40 px-7 py-3.5 text-sm font-medium text-app-text backdrop-blur-sm transition hover:border-white/35 hover:bg-white/10"
                >
                  Explore NERO
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
