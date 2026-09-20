import { Bot } from "lucide-react";

/**
 * The System section's NERO figure.
 *
 * Placeholder pending the approved "Page 2 Explainer Pose" export (Figma
 * node 103:12) — this environment's network policy blocks fetching Figma
 * asset bytes directly, so this renders an abstract on-brand mark in the
 * same slot/scale instead of reusing the Page 1 standing-pose artwork.
 * Swap the contents of the figure element below for an <Image> of the
 * real export (once saved under /public/brand) — the surrounding
 * glow/floor treatment does not need to change.
 */
export default function NeroSystemVisual() {
  return (
    <div className="relative mx-auto w-full max-w-[280px] sm:max-w-[320px]">
      <div
        className="nero-float relative z-10 aspect-[390/468] w-full"
        role="img"
        aria-label="NERO, the AI Job Intelligence mascot, in a presenting pose explaining the Discover, Match, ATS, and Optimize system"
      >
        <div
          className="absolute inset-x-[14%] bottom-[8%] top-[22%] -rotate-6 rounded-[45%] bg-gradient-to-b from-crimson-fill/60 to-crimson-fill/10 blur-[1px]"
          aria-hidden="true"
        />

        <div className="absolute inset-[8%] rounded-[42%] border-2 border-app-blue/70 bg-gradient-to-b from-app-panel-strong to-app-bg shadow-[0_24px_50px_rgba(0,0,0,0.55)]" />

        <Bot
          className="absolute inset-0 m-auto h-[44%] w-[44%] text-app-text drop-shadow-[0_0_24px_rgba(10,132,255,0.45)]"
          strokeWidth={1.5}
          aria-hidden="true"
        />

        <span
          className="absolute left-[12%] top-[12%] h-2 w-2 rounded-full bg-app-red shadow-[0_0_10px_rgba(255,59,48,0.7)]"
          aria-hidden="true"
        />
      </div>

      <div
        className="nero-floor-glow pointer-events-none absolute -bottom-4 left-1/2 h-20 w-[85%] -translate-x-1/2"
        aria-hidden="true"
      />
    </div>
  );
}
