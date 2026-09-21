import type { CSSProperties } from "react";
import Image from "next/image";

/**
 * The finale's NERO — the same approved standing/pointing artwork used
 * everywhere else on the page (no new pose, no new character).
 *
 * Success beat, and the page's closing gesture: the thumbs-up in this
 * pose is what "Same You. A Brighter Tomorrow." is being said over, so
 * the figure holds the foreground of the widest scene on the page. The
 * cadence stays deliberately calm (6.4s / 16px against the 6s / 14px
 * default): slightly more lift than flat, but nothing like the bounce
 * Meet NERO gets — this scene's brief is to slow the rhythm down, not
 * to end on another burst of motion.
 *
 * Lives in its own component (rather than inside NeroFinaleVisual, as
 * it did before the full-bleed pass) because the environment behind it
 * is now edge-to-edge while NERO belongs to the composition's measure:
 * he is a real column of .finale-stage next to the copy instead of an
 * absolutely-placed layer pinned to the viewport edge.
 */
export default function NeroFinaleFigure() {
  return (
    <div
      data-parallax-speed="0.14"
      data-parallax-scale-to="1.06"
      data-parallax-local
      className="relative mx-auto w-[52%] max-w-[190px] sm:max-w-[230px] lg:mx-0 lg:w-full lg:max-w-[320px]"
    >
      <Image
        src="/brand/nero-hero-figure.png"
        alt="NERO, the AI Job Intelligence mascot, giving a thumbs up as he looks out over the horizon toward what's next"
        width={1098}
        height={1334}
        sizes="(min-width: 1024px) 320px, (min-width: 640px) 230px, 190px"
        quality={95}
        style={
          {
            "--nero-float-duration": "6.4s",
            "--nero-float-distance": "16px",
          } as CSSProperties
        }
        className="nero-float relative z-10 h-auto w-full drop-shadow-[0_30px_60px_rgba(0,0,0,0.6)]"
      />
      <div
        className="nero-floor-glow pointer-events-none absolute -bottom-4 left-1/2 h-16 w-[85%] -translate-x-1/2"
        aria-hidden="true"
      />
    </div>
  );
}
