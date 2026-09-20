import {
  ChevronDown,
  Eye,
  Mouse,
  ShieldCheck,
  SlidersHorizontal,
  User,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import NeroNextMoveVisual from "@/components/app/nero-next-move-visual";

const principles: {
  icon: LucideIcon;
  title: string;
  text: string;
}[] = [
  {
    icon: User,
    title: "PERSONAL",
    text: "Your resume, experience, skills, titles, and preferences shape the search.",
  },
  {
    icon: ShieldCheck,
    title: "TRUTHFUL",
    text: "Recommendations improve your existing qualifications without fabricating experience.",
  },
  {
    icon: Eye,
    title: "TRANSPARENT",
    text: "Every match and recommendation should have a reason behind it.",
  },
  {
    icon: SlidersHorizontal,
    title: "USER CONTROLLED",
    text: "The system helps you decide. It does not blindly apply to jobs for you.",
  },
];

const PROGRESS_STEPS = ["01", "02", "03", "04", "05", "06"];
const ACTIVE_STEP = "05";

/**
 * Page 5 — "Make Your Next Move." (Principles).
 *
 * Same world as the hero/system/job-intelligence scenes before it: same
 * background, technical grid, atmospheric lighting recipe, NERO figure,
 * type scale, and micro-labels — the atmosphere blend just shifts
 * weight toward red here as the scroll journey approaches the final
 * CTA's red-atmosphere. Built in the same distinct layers (background /
 * environment / copy+NERO / principle cards / foreground details) as
 * Page 4 so a future scroll-driven parallax can target each one the
 * same way.
 */
export default function NeroNextMoveSection() {
  return (
    <section
      id="resources"
      className="relative overflow-hidden border-t border-white/10 bg-[#0a0d13]"
    >
      {/* Layer 1 — background */}
      <div className="technical-grid absolute inset-0 opacity-30" aria-hidden="true" />
      <div className="next-move-atmosphere absolute inset-0" aria-hidden="true" />

      {/* Layer 2 — environment (subtle architectural shapes) */}
      <div
        className="pointer-events-none absolute -right-40 top-16 hidden h-[440px] w-[440px] rounded-full border border-white/5 bg-[radial-gradient(circle_at_40%_40%,rgba(255,59,48,0.08),transparent_62%)] lg:block"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute left-[10%] top-20 hidden h-px w-32 -rotate-[28deg] bg-gradient-to-r from-transparent via-app-blue/40 to-transparent lg:block"
        aria-hidden="true"
      />

      <div className="relative mx-auto max-w-[1536px] px-6 py-16 sm:px-10 sm:py-20 lg:px-20 lg:py-28">
        <div className="grid gap-14 lg:grid-cols-[minmax(0,480px)_1fr] lg:gap-16 xl:grid-cols-[minmax(0,540px)_1fr]">
          {/* LEFT — copy + NERO */}
          <div className="flex flex-col">
            <div className="flex items-center gap-3">
              <span className="mono text-[10px] tracking-[0.3em] text-app-red">
                05 / 06 &nbsp; MAKE YOUR NEXT MOVE
              </span>
              <span className="h-px w-12 bg-app-border-strong" />
            </div>

            <h2 className="mt-5 font-[family-name:var(--font-display)] text-[clamp(2.5rem,5vw,3.75rem)] font-extrabold leading-[0.95] tracking-[-0.03em] text-app-text">
              MAKE YOUR
              <br />
              NEXT{" "}
              <span className="bg-gradient-to-r from-[#8f7bff] via-[#b46bff] to-app-red bg-clip-text text-transparent">
                MOVE.
              </span>
            </h2>

            <p className="mt-6 max-w-[470px] text-base leading-7 text-app-muted sm:text-lg">
              Every recommendation follows the same four rules — so
              whatever you decide next, it&apos;s actually yours.
            </p>

            <div className="relative mt-6 w-fit">
              <p className="font-[family-name:var(--font-caveat)] text-2xl leading-[1.15] text-app-blue sm:text-[26px]">
                Your Terms.
                <br />
                Your Career.
              </p>
              <span
                className="absolute -bottom-1 left-0 h-0.5 w-24 -rotate-6 bg-app-red/80"
                aria-hidden="true"
              />
            </div>

            <div className="relative mx-auto mt-10 w-full max-w-[280px] sm:max-w-[320px] lg:mt-12 lg:max-w-[340px]">
              <NeroNextMoveVisual />
            </div>
          </div>

          {/* RIGHT — four principle cards */}
          <div className="grid gap-6 sm:grid-cols-2">
            {principles.map((principle, index) => (
              <PrincipleCard key={principle.title} {...principle} index={index} />
            ))}
          </div>
        </div>

        {/* Foreground detail — bottom utility bar, same structure as Page 4's */}
        <div className="relative mt-16 flex flex-col items-center gap-5 border-t border-white/5 pt-6 text-center lg:mt-20 lg:flex-row lg:justify-between lg:text-left">
          <ProgressRail />

          <div className="flex flex-col items-center gap-2">
            <span className="mono text-[9px] tracking-[0.3em] text-app-muted">
              SCROLL TO CONTINUE
            </span>
            <Mouse className="h-4 w-4 text-app-muted" aria-hidden="true" />
            <ChevronDown
              className="scroll-dot -mt-1.5 h-3 w-3 text-app-muted"
              aria-hidden="true"
            />
          </div>

          <div className="mono text-[9px] leading-5 tracking-[0.2em] text-app-muted">
            YOUR TERMS.
            <br />
            YOUR NEXT MOVE.
          </div>
        </div>
      </div>
    </section>
  );
}

function PrincipleCard({
  icon: Icon,
  title,
  text,
  index,
}: {
  icon: LucideIcon;
  title: string;
  text: string;
  index: number;
}) {
  return (
    <div
      className="system-card-reveal glass-panel relative rounded-2xl border border-app-border-soft p-5 shadow-[0_0_24px_-14px_rgba(255,59,48,0.4)]"
      style={{ animationDelay: `${index * 100}ms` }}
    >
      <div className="flex h-11 w-11 items-center justify-center rounded-full border border-app-border-soft text-app-blue">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </div>

      <h3 className="mt-4 text-sm font-semibold tracking-[0.15em] text-app-text">
        {title}
      </h3>

      <p className="mt-2 text-sm leading-6 text-app-muted">{text}</p>
    </div>
  );
}

function ProgressRail() {
  const activeIndex = PROGRESS_STEPS.indexOf(ACTIVE_STEP);
  const activePercent = (activeIndex / (PROGRESS_STEPS.length - 1)) * 100;

  return (
    <div className="flex flex-col items-center gap-2.5 lg:items-start" aria-hidden="true">
      <div className="relative h-px w-40 bg-app-border-soft">
        <span
          className="absolute -top-[3px] h-[7px] w-[7px] -translate-x-1/2 rounded-full bg-gradient-to-r from-app-blue to-[#8f5cff] shadow-[0_0_10px_rgba(143,92,255,0.7)]"
          style={{ left: `${activePercent}%` }}
        />
      </div>

      <div className="flex items-center gap-3">
        {PROGRESS_STEPS.map((step) => (
          <span
            key={step}
            className={cn(
              "mono text-[10px] tracking-[0.1em]",
              step === ACTIVE_STEP ? "text-app-text" : "text-app-muted/50",
            )}
          >
            {step}
          </span>
        ))}
      </div>
    </div>
  );
}
