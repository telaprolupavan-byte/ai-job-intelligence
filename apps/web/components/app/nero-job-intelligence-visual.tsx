import Image from "next/image";

/**
 * The "Job Intelligence" (Page 4) NERO figure — reuses the same
 * approved standing/pointing artwork as the hero (no new pose is
 * generated), restyled with atmosphere/glow and a speech-bubble
 * annotation so it reads as NERO "connecting the dots" between the
 * surrounding input panels.
 */
export default function NeroJobIntelligenceVisual() {
  return (
    <div className="relative mx-auto w-full max-w-[250px] sm:max-w-[320px] lg:max-w-[380px]">
      <div
        className="pointer-events-none absolute -top-8 right-[-10%] z-20 hidden max-w-[190px] rotate-2 sm:block"
        aria-hidden="true"
      >
        <div className="relative rounded-2xl border border-app-border-soft bg-app-panel/85 px-4 py-3 shadow-lg backdrop-blur-sm">
          <p className="font-[family-name:var(--font-caveat)] text-xl leading-5 text-app-text">
            Let me connect the dots.
          </p>
          <span
            className="absolute -bottom-1.5 left-9 h-3.5 w-3.5 rotate-45 border-b border-r border-app-border-soft bg-app-panel/85"
            aria-hidden="true"
          />
        </div>
      </div>

      <Image
        src="/brand/nero-hero-figure.png"
        alt="NERO, the AI Job Intelligence mascot, connecting the pieces of an opportunity together"
        width={1098}
        height={1334}
        sizes="(min-width: 1024px) 340px, (min-width: 640px) 300px, 230px"
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
