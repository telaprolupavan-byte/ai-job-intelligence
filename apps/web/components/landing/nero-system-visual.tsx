import type { CSSProperties } from "react";
import Image from "next/image";

/**
 * The System section's NERO figure — the approved "Page 2 Explainer Pose"
 * export (Figma node 103:12), distinct from the Page 1 standing/pointing
 * artwork.
 *
 * Character pass: this is NERO's introduction, so it carries the most
 * personality of any scene on the page. The explainer pose already has
 * him mid-sentence — finger up, live panel in the other hand — and the
 * treatment leans into it rather than presenting him neutrally:
 *  - the largest figure outside the hero, so he owns the left column
 *    instead of sitting under the handwritten notes as a footnote;
 *  - the quickest, deepest idle float on the page (4.6s / 18px against
 *    the 6s / 14px default), which reads as someone bouncing on their
 *    heels while explaining rather than hovering;
 *  - a small counter-clockwise lean on the wrapper — he's tilting into
 *    the four system cards on the right, mid-explanation.
 * The lean lives on the wrapper because .nero-float animates the
 * figure's own `transform`, and a utility rotate on that same element
 * would be overwritten every frame.
 */
export default function NeroSystemVisual() {
  return (
    <div className="relative mx-auto w-full -rotate-[1.5deg]">
      <Image
        src="/brand/nero-page2-explainer.png"
        alt="NERO, the AI Job Intelligence mascot, in a presenting pose explaining the Discover, Match, ATS, and Optimize system"
        width={780}
        height={936}
        sizes="(min-width: 1024px) 400px, (min-width: 640px) 360px, 300px"
        quality={95}
        style={
          {
            "--nero-float-duration": "4.6s",
            "--nero-float-distance": "18px",
          } as CSSProperties
        }
        className="nero-float relative z-10 h-auto w-full drop-shadow-[0_30px_60px_rgba(0,0,0,0.55)]"
      />

      <div
        className="nero-floor-glow pointer-events-none absolute -bottom-4 left-1/2 h-20 w-[85%] -translate-x-1/2"
        aria-hidden="true"
      />
    </div>
  );
}
