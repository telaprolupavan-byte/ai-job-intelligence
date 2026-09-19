import Image from "next/image";
import { Sora } from "next/font/google";

// The NERO wordmark is set in Sora per the approved brand system (Figma:
// "AI Job Intelligence — Product Design" → 00 - Brand & Design System →
// NERO — APPROVED PRIMARY LOGO). Loaded here rather than in the root
// layout since it is only ever used for this lockup.
const sora = Sora({
  subsets: ["latin"],
  weight: ["600", "800"],
  display: "swap",
});

const SIZES = {
  default: {
    icon: 40,
    nero: "text-lg",
    descriptor: "text-[9px] tracking-[0.16em]",
    gapX: "gap-2.5",
  },
  sm: {
    icon: 32,
    nero: "text-base",
    descriptor: "text-[8px] tracking-[0.14em]",
    gapX: "gap-2",
  },
} as const;

type NeroBrandProps = {
  size?: keyof typeof SIZES;
  className?: string;
};

export default function NeroBrand({
  size = "default",
  className = "",
}: NeroBrandProps) {
  const s = SIZES[size];

  return (
    <span className={`inline-flex items-center ${s.gapX} ${className}`}>
      <Image
        src="/brand/nero-mark.svg"
        alt=""
        width={s.icon}
        height={s.icon}
        className="shrink-0"
        priority
      />

      <span className={`flex flex-col justify-center gap-0.5 ${sora.className}`}>
        <span
          className={`${s.nero} font-extrabold leading-none text-white`}
        >
          NERO
        </span>

        <span
          className={`${s.descriptor} font-semibold uppercase leading-none text-[#00D9FF]`}
        >
          AI JOB INTELLIGENCE
        </span>
      </span>
    </span>
  );
}
