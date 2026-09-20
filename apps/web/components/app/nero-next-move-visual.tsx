import Image from "next/image";

/**
 * Page 5's NERO figure — reuses the same approved standing/pointing
 * artwork as the hero and Job Intelligence scenes (no new pose is
 * generated), with a speech-bubble annotation that hands the moment
 * back to the visitor at the decision point.
 */
export default function NeroNextMoveVisual() {
  return (
    <div className="relative mx-auto w-full max-w-[360px]">
      <div
        className="pointer-events-none absolute -top-4 left-[-4%] z-20 hidden max-w-[180px] -rotate-2 sm:block"
        aria-hidden="true"
      >
        <div className="relative rounded-2xl border border-app-border-soft bg-app-panel/85 px-4 py-3 shadow-lg backdrop-blur-sm">
          <p className="font-[family-name:var(--font-caveat)] text-xl leading-5 text-app-text">
            Your call. I&apos;ve got you covered.
          </p>
          <span
            className="absolute -bottom-1.5 right-9 h-3.5 w-3.5 rotate-45 border-b border-r border-app-border-soft bg-app-panel/85"
            aria-hidden="true"
          />
        </div>
      </div>

      <Image
        src="/brand/nero-hero-figure.png"
        alt="NERO, the AI Job Intelligence mascot, standing ready as you decide your next move"
        width={1098}
        height={1334}
        sizes="(min-width: 1024px) 320px, (min-width: 640px) 280px, 220px"
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
