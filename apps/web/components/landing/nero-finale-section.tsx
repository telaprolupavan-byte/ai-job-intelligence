import type { CSSProperties } from "react";
import Link from "next/link";
import NeroFinaleVisual from "@/components/landing/nero-finale-visual";
import NeroFinaleFigure from "@/components/landing/nero-finale-figure";

/**
 * "Same You. A Brighter Tomorrow." — the page's cinematic finale and
 * final conversion moment, and the last section before the footer.
 *
 * STRONGEST closing tier: eyebrow -> headline -> subtext -> CTA stage
 * in with increasing delay so the CTA is the last thing to fully
 * arrive, over a layered parallax environment (sky, horizon, ridges,
 * skyline, NERO) that recedes behind it.
 *
 * Final visual pass: the scene used to live inside a rounded, bordered
 * card floating in the middle of a padded section, which framed the
 * page's closing moment as one more panel in a stack of panels — a
 * boxed CTA rather than a conclusion. The environment is now full
 * bleed: it runs edge to edge as the section itself, the copy sits on
 * the same measure (.landing-shell) as every other section so the
 * finale still belongs to the page's grid, and the section carries a
 * viewport-scaled minimum height so the horizon has room to read as a
 * horizon.
 *
 * NERO moved with it. He used to be anchored to the card's left edge
 * inside the backdrop component, which on a wide screen parked him
 * against the viewport edge with no relationship to the words. He is
 * now the stage's own left zone — one grid, figure and copy sharing a
 * centre line — so the closing composition reads as NERO looking out
 * over the horizon beside the sentence he is there to deliver.
 */
export default function NeroFinaleSection() {
  return (
    <section
      id="pricing"
      className="finale-section relative overflow-hidden border-t border-white/10 bg-[#0a0d13]"
    >
      <NeroFinaleVisual />

      <div className="landing-shell finale-band relative z-10">
        <div
          data-parallax-speed="0.05"
          data-parallax-local
          className="pointer-events-none absolute left-6 top-8 z-20 max-w-[170px] -rotate-2 sm:left-10 sm:top-10 lg:left-16"
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
          className="pointer-events-none absolute right-6 top-8 z-20 hidden max-w-[190px] rotate-2 text-right sm:right-10 sm:top-10 sm:block lg:right-16"
          aria-hidden="true"
        >
          <p className="nero-note text-app-text/90">
            More Opportunities.
            <br />
            A Brighter You.
          </p>
        </div>

        <div className="finale-stage relative z-10">
          {/* NERO's zone — a real column of the stage at every width,
              bottom-aligned so he stands on the ridge line behind him
              rather than floating in the middle of the sky. */}
          <div className="finale-stage-figure">
            <NeroFinaleFigure />
          </div>

          <div className="finale-stage-copy flex flex-col items-center text-center">
            <div data-reveal className="flex items-center gap-3">
              <span
                className="hidden h-px w-10 bg-app-red/50 sm:block"
                aria-hidden="true"
              />
              <span className="mono text-[10px] tracking-[0.3em] text-app-red">
                IT&apos;S MORE THAN A JOB.
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
    </section>
  );
}
