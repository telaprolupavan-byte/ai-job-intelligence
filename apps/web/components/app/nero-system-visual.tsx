import Image from "next/image";

/**
 * The System section's NERO figure — the approved "Page 2 Explainer Pose"
 * export (Figma node 103:12), distinct from the Page 1 standing/pointing
 * artwork.
 */
export default function NeroSystemVisual() {
  return (
    <div className="relative mx-auto w-full">
      <Image
        src="/brand/nero-page2-explainer.png"
        alt="NERO, the AI Job Intelligence mascot, in a presenting pose explaining the Discover, Match, ATS, and Optimize system"
        width={780}
        height={936}
        sizes="(min-width: 1024px) 360px, (min-width: 640px) 320px, 280px"
        quality={95}
        className="nero-float relative z-10 h-auto w-full drop-shadow-[0_30px_60px_rgba(0,0,0,0.55)]"
      />

      <div
        className="nero-floor-glow pointer-events-none absolute -bottom-4 left-1/2 h-20 w-[85%] -translate-x-1/2"
        aria-hidden="true"
      />
    </div>
  );
}
