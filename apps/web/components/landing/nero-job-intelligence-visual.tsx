import type { CSSProperties } from "react";
import Image from "next/image";

/**
 * The "Job Intelligence" (Page 4) NERO figure — reuses the same
 * approved standing/pointing artwork as the hero (no new pose is
 * generated), restyled with atmosphere/glow and a speech-bubble
 * annotation so it reads as NERO "connecting the dots" between the
 * surrounding input panels.
 *
 * Character pass: the MATCHING beat. The pointing arm in this pose aims
 * at the input panels stacked to his left while the clarity object
 * resolves on his right, so he sits at the junction doing the joining —
 * the figure is sized up a step so he reads as the mechanism between
 * the two columns rather than a decoration parked between them. Idle
 * float is a touch quicker and deeper than the default (5.4s / 16px):
 * actively working the two sides together.
 */
export default function NeroJobIntelligenceVisual() {
  return (
    <div className="relative mx-auto w-full max-w-[270px] sm:max-w-[340px] lg:max-w-[400px]">
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
        sizes="(min-width: 1024px) 400px, (min-width: 640px) 340px, 270px"
        quality={95}
        style={
          {
            "--nero-float-duration": "5.4s",
            "--nero-float-distance": "16px",
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
