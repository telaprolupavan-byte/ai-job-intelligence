/**
 * The hero's centerpiece NERO character.
 *
 * Placeholder pending the production GLB -> react-three-fiber pipeline
 * (see landing page task notes): renders a cropped frame of the single
 * approved NERO artwork sprite so the visual slot, sizing, and glow
 * treatment are already correct. Swap the figure element below for the
 * <Canvas> render once the optimized GLB is ready — the surrounding
 * atmosphere/annotation/panel do not need to change.
 */
export default function NeroHeroVisual() {
  return (
    <div className="relative mx-auto w-full max-w-[500px]">
      <div
        className="nero-hero-figure nero-float relative z-10 w-full drop-shadow-[0_30px_60px_rgba(0,0,0,0.55)]"
        role="img"
        aria-label="NERO, the AI Job Intelligence mascot, giving a thumbs up in a superhero pose"
      />

      <div
        className="nero-floor-glow pointer-events-none absolute -bottom-6 left-1/2 h-24 w-[85%] -translate-x-1/2"
        aria-hidden="true"
      />
    </div>
  );
}
