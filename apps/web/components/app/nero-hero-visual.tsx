import Image from "next/image";

/**
 * The hero's centerpiece NERO character.
 *
 * Placeholder pending the production GLB -> react-three-fiber pipeline
 * (see landing page task notes): renders the approved standing-pose
 * NERO artwork so the visual slot, sizing, and glow treatment are
 * already correct. Swap the figure element below for the <Canvas>
 * render once the optimized GLB is ready — the surrounding
 * atmosphere/annotation/panel do not need to change.
 *
 * Perf note: this used to be a CSS `background-image` (.nero-hero-figure)
 * pointing straight at the 1.37MB source PNG, which meant it bypassed
 * the image pipeline entirely — the browser downloaded the full
 * 1098x1334 original, unresized and in PNG, for every viewport, and it
 * was the page's LCP element. The class applied `background-size: 100%
 * 100%` at `0 0`, i.e. no crop at all, so an <Image> is pixel-identical
 * while getting responsive sizing, AVIF/WebP and lazy-loading below the
 * fold. Same approved artwork, same framing.
 */
export default function NeroHeroVisual({
  priority = false,
}: {
  priority?: boolean;
}) {
  return (
    <div className="relative mx-auto w-full max-w-[480px]">
      <Image
        src="/brand/nero-hero-figure.png"
        alt="NERO, the AI Job Intelligence mascot, pointing at the viewer with a thumbs up in a superhero pose"
        width={1098}
        height={1334}
        sizes="(min-width: 1024px) 480px, (min-width: 640px) 400px, 280px"
        quality={90}
        priority={priority}
        className="nero-float relative z-10 h-auto w-full drop-shadow-[0_30px_60px_rgba(0,0,0,0.55)]"
      />

      <div
        className="nero-floor-glow pointer-events-none absolute -bottom-6 left-1/2 h-24 w-[85%] -translate-x-1/2"
        aria-hidden="true"
      />
    </div>
  );
}
