import Image from "next/image";

/**
 * Page 5's closing environment — "Same You. A Brighter Tomorrow."
 *
 * Reuses the same approved standing/pointing NERO artwork as every
 * other scene (no new character, no new pose, no new logo mark),
 * staged over a CSS/SVG-built ridge that recedes toward a distant
 * skyline so the finale reads as NERO looking out over what's next.
 * Same layering technique as the Job Intelligence data streams
 * (gradient-stroked SVG path, dash-offset flow) and the same
 * nero-float / nero-floor-glow treatment used throughout the site.
 *
 * Depth pass: the finale had zero scroll-linked motion of its own
 * (every other scene has at least atmosphere parallax) — every layer
 * now carries its own independent speed, slowest to fastest: sky
 * (background) < horizon glow < ridge-back < ridge-mid < city <
 * planet < ridge-front < NERO (foreground), so the scene reads as
 * genuine receding depth rather than one flat backdrop image. Kept
 * gentle relative to earlier scenes per the brief's "slow the visual
 * rhythm" — this is the closing moment, not another burst of motion.
 */
export default function NeroFinaleVisual() {
  return (
    <div className="absolute inset-0 overflow-hidden">
      {/* VERY HIGH tier — the page's strongest cinematic scene, and the
          one section with no motion at all before this pass. Layered
          local parallax, slowest to fastest: sky (background) <
          horizon glow (atmosphere) < planet (midground) < NERO below,
          each restrained enough to stay premium rather than showy. */}
      <div
        data-parallax-speed="0.04"
        data-parallax-local
        className="finale-sky absolute inset-0"
        aria-hidden="true"
      />
      <div
        data-parallax-speed="0.07"
        data-parallax-local
        className="finale-horizon-glow absolute inset-x-0 bottom-0 h-2/3"
        aria-hidden="true"
      />
      <div
        data-parallax-speed="0.1"
        data-parallax-x="-0.02"
        data-parallax-scale-to="1.06"
        data-parallax-local
        className="finale-planet absolute -right-10 -top-10 h-40 w-40 rounded-full sm:h-56 sm:w-56 lg:h-64 lg:w-64"
        aria-hidden="true"
      />

      <svg
        className="absolute inset-0 h-full w-full"
        viewBox="0 0 400 200"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="finale-road-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#ff3b30" stopOpacity="0.85" />
            <stop offset="55%" stopColor="#ff9500" stopOpacity="0.7" />
            <stop offset="100%" stopColor="#ffd9a8" stopOpacity="0.45" />
          </linearGradient>
        </defs>

        <path
          data-parallax-speed="0.015"
          data-parallax-local
          className="finale-ridge-back"
          d="M0,140 L20,120 L45,132 L70,110 L95,128 L120,105 L150,125 L180,115 L210,130 L240,112 L270,128 L300,118 L330,132 L360,122 L400,135 L400,200 L0,200 Z"
        />
        <path
          data-parallax-speed="0.028"
          data-parallax-local
          className="finale-ridge-mid"
          d="M0,160 L30,150 L60,165 L90,145 L130,162 L170,148 L210,166 L250,150 L290,168 L330,155 L360,170 L400,160 L400,200 L0,200 Z"
        />

        <g
          data-parallax-speed="0.035"
          data-parallax-local
          className="finale-city"
        >
          <rect x="228" y="150" width="10" height="22" />
          <rect x="242" y="140" width="8" height="32" />
          <rect x="254" y="152" width="12" height="20" />
          <rect x="270" y="135" width="9" height="37" />
          <rect x="283" y="148" width="7" height="24" />
          <rect x="294" y="142" width="11" height="30" />
          <rect x="309" y="155" width="8" height="17" />
          <rect x="321" y="145" width="10" height="27" />
          <rect x="335" y="150" width="7" height="22" />
        </g>
        <g className="finale-city-glow">
          <circle cx="233" cy="158" r="0.9" />
          <circle cx="246" cy="150" r="0.9" />
          <circle cx="260" cy="160" r="0.9" />
          <circle cx="274" cy="146" r="0.9" />
          <circle cx="298" cy="152" r="0.9" />
          <circle cx="313" cy="162" r="0.9" />
          <circle cx="326" cy="154" r="0.9" />
        </g>

        <path
          data-parallax-speed="0.045"
          data-parallax-local
          className="finale-ridge-front"
          d="M0,92 C40,82 72,96 102,122 C142,152 202,176 262,186 C312,193 362,197 400,199 L400,200 L0,200 Z"
        />

        <path
          className="finale-road finale-road-animated"
          d="M 68 197 C 128 190, 150 170, 192 165 S 262 172, 300 172"
        />
      </svg>

      <div className="finale-scrim absolute inset-0" aria-hidden="true" />

      <div
        data-parallax-speed="0.14"
        data-parallax-scale-to="1.06"
        data-parallax-local
        className="absolute bottom-0 left-[3%] z-10 w-[46%] max-w-[190px] sm:max-w-[230px] lg:left-6 lg:w-[300px] lg:max-w-[300px]"
      >
        <Image
          src="/brand/nero-hero-figure.png"
          alt="NERO, the AI Job Intelligence mascot, looking out over the horizon toward what's next"
          width={1098}
          height={1334}
          sizes="(min-width: 1024px) 300px, (min-width: 640px) 230px, 190px"
          quality={95}
          className="nero-float relative h-auto w-full drop-shadow-[0_30px_60px_rgba(0,0,0,0.6)]"
        />
        <div
          className="nero-floor-glow pointer-events-none absolute -bottom-4 left-1/2 h-16 w-[85%] -translate-x-1/2"
          aria-hidden="true"
        />
      </div>
    </div>
  );
}
