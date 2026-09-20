import Link from "next/link";
import {
  Activity,
  BarChart3,
  Bookmark,
  Check,
  ChevronDown,
  FileCheck2,
  Lightbulb,
  ListChecks,
  MapPin,
  Mouse,
  Search,
  Target,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import Badge from "@/components/app/badge";
import NeroNextMoveVisual from "@/components/app/nero-next-move-visual";
import NeroFinaleVisual from "@/components/app/nero-finale-visual";

const insightStats: { icon: LucideIcon; title: string; text: string }[] = [
  {
    icon: FileCheck2,
    title: "Resume optimized",
    text: "Tightened and aligned to the roles you're actually going after.",
  },
  {
    icon: Search,
    title: "Relevant roles",
    text: "Surfaced from live listings, not just keyword matches.",
  },
  {
    icon: BarChart3,
    title: "Match scores",
    text: "A clear read on fit before you spend time applying.",
  },
  {
    icon: ListChecks,
    title: "Applications organized",
    text: "Every application, every stage, in one place.",
  },
];

const valueItems: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: Bookmark, title: "Stay Organized", text: "Every saved role in one place." },
  { icon: Activity, title: "Track Progress", text: "Know where each application stands." },
  { icon: BarChart3, title: "Get Insights", text: "Understand your fit before you apply." },
  { icon: TrendingUp, title: "Move Forward", text: "Turn intelligence into your next step." },
];

const APPLICATION_STAGES = ["Saved", "Applied", "Screening", "Interview", "Offer"];
const CURRENT_STAGE = "Screening";

const PROGRESS_STEPS = ["01", "02", "03", "04", "05", "06"];
const ACTIVE_STEP = "05";

/**
 * Page 5 — "Make Your Next Move." Hero / Application in Progress /
 * Insights / Value Row. Reuses Page 4's exact motion language — same
 * technical-grid + atmosphere background, same system-card-reveal
 * entrance animation, same NERO float/glow treatment — and the same
 * site-wide 01-06 progress rail Page 4 ends on, now with 05 active.
 *
 * The standalone five-step "Save / Apply / Track / Prepare / Achieve"
 * journey sub-scene that used to sit here was removed as duplicate
 * content once the dedicated eight-step NERO Journey section (Resume
 * -> Understand -> Discover -> Match -> Improve -> Verify -> Apply ->
 * Track) became the page's single primary journey visualization; the
 * Hero's "See It in Action" link now points there instead.
 *
 * The cinematic "Same You. A Brighter Tomorrow." finale that used to
 * close this section is exported separately below as
 * `NeroFinaleSection` — same file, same content, unchanged — so
 * page.tsx can position it as the page's true final section, after
 * For Students / For Consultancies, per the approved landing-page
 * story order.
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
        {/* Foreground detail — top-right handwritten annotation, same
            motif as the hero/job-intel scenes above it. */}
        <div
          className="pointer-events-none absolute right-6 top-10 z-20 hidden max-w-[180px] -rotate-2 text-right sm:right-10 lg:right-20 lg:block"
          aria-hidden="true"
        >
          <p className="font-[family-name:var(--font-caveat)] text-2xl leading-[1.15] text-app-text/90">
            Every
            <br />
            Move Counts.
          </p>
        </div>

        {/* ------------------------------------------------------ */}
        {/* A — HERO                                                */}
        {/* ------------------------------------------------------ */}
        <div>
          <div className="flex items-center gap-3">
            <span className="mono text-[10px] tracking-[0.3em] text-app-red">
              05 / 05 &nbsp; YOUR NEXT MOVE
            </span>
            <span className="h-px w-12 bg-app-red/50" />
          </div>

          <div className="mt-10 grid gap-14 lg:grid-cols-[minmax(0,560px)_1fr] lg:items-center lg:gap-16">
            <div>
              <h2 className="font-[family-name:var(--font-display)] text-[clamp(2.75rem,6vw,4.5rem)] font-extrabold leading-[0.95] tracking-[-0.03em] text-app-text">
                MAKE YOUR
                <br />
                NEXT{" "}
                <span className="bg-gradient-to-r from-[#8f7bff] via-[#b46bff] to-app-red bg-clip-text text-transparent">
                  MOVE.
                </span>
              </h2>

              <p className="mt-6 max-w-[520px] text-base leading-7 text-app-muted sm:text-lg">
                Discover, match, and prepare are only the beginning. Now
                it&apos;s time to apply, track, and follow through — with
                NERO alongside you the whole way.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  href="/register"
                  className="app-focus-ring group inline-flex items-center justify-center gap-2 rounded-lg bg-crimson-fill px-6 py-3.5 text-sm font-medium text-white shadow-[0_0_28px_rgba(217,40,31,0.4)] transition hover:bg-crimson-fill-hover"
                >
                  Get Started
                  <span className="transition-transform group-hover:translate-x-1">
                    →
                  </span>
                </Link>

                <Link
                  href="#nero-journey"
                  className="app-focus-ring inline-flex items-center justify-center rounded-lg border border-app-border-soft bg-white/[0.02] px-6 py-3.5 text-sm font-medium text-app-text transition hover:bg-white/[0.05]"
                >
                  See It in Action
                </Link>
              </div>
            </div>

            <div className="relative mx-auto w-full max-w-[320px] sm:max-w-[360px]">
              <div className="pointer-events-none absolute -top-6 right-[-4%] z-20 hidden sm:block">
                <FloatingStat icon={FileCheck2} label="RESUME READY" />
              </div>
              <div className="pointer-events-none absolute left-[-12%] top-24 z-20 hidden sm:block">
                <FloatingStat icon={Target} label="94% MATCH" />
              </div>
              <div className="pointer-events-none absolute bottom-2 right-[-6%] z-20 hidden sm:block">
                <FloatingStat icon={ListChecks} label="APPLICATION TRACKED" />
              </div>

              <NeroNextMoveVisual />
            </div>
          </div>
        </div>

        {/* ------------------------------------------------------ */}
        {/* B — APPLICATION IN PROGRESS                             */}
        {/* ------------------------------------------------------ */}
        <div id="next-move-progress" className="mt-24 scroll-mt-24 lg:mt-32">
          <div className="flex items-center gap-3">
            <span className="mono text-[10px] tracking-[0.3em] text-app-red">
              APPLICATION IN PROGRESS
            </span>
            <span className="h-px w-12 bg-app-border-strong" />
          </div>

          <h3 className="mt-5 max-w-xl font-[family-name:var(--font-display)] text-3xl font-bold tracking-[-0.02em] text-app-text sm:text-4xl">
            See exactly where you stand.
          </h3>

          <div className="mt-10 max-w-2xl">
            <ApplicationInProgressCard />
          </div>
        </div>

        {/* ------------------------------------------------------ */}
        {/* C — NERO INSIGHTS                                       */}
        {/* ------------------------------------------------------ */}
        <div id="next-move-insights" className="mt-24 scroll-mt-24 lg:mt-32">
          <div className="flex items-center gap-3">
            <span className="mono text-[10px] tracking-[0.3em] text-app-red">
              NERO INSIGHTS
            </span>
            <span className="h-px w-12 bg-app-border-strong" />
          </div>

          <h3 className="mt-5 max-w-xl font-[family-name:var(--font-display)] text-3xl font-bold tracking-[-0.02em] text-app-text sm:text-4xl">
            You&apos;re on the right track.
          </h3>

          <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {insightStats.map((stat, index) => (
              <InsightTile key={stat.title} {...stat} index={index} />
            ))}
          </div>

          <p className="mx-auto mt-14 max-w-lg text-center font-[family-name:var(--font-caveat)] text-2xl leading-[1.2] text-app-blue sm:text-[26px]">
            NERO gives you the clarity. The decision is yours.
          </p>
        </div>

        {/* ------------------------------------------------------ */}
        {/* D — SUPPORTING VALUE ROW                                */}
        {/* ------------------------------------------------------ */}
        <div id="next-move-value" className="mt-24 scroll-mt-24 border-t border-white/10 pt-14 lg:mt-32">
          <div className="grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-4">
            {valueItems.map((item, index) => (
              <FeatureTile key={item.title} {...item} index={index} />
            ))}
          </div>
        </div>

        {/* ------------------------------------------------------ */}
        {/* Foreground detail — bottom utility bar, the site-wide   */}
        {/* 01-06 progress rail (05 active), transitioning into the */}
        {/* Student / Consultancy chapters that follow.             */}
        {/* ------------------------------------------------------ */}
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
            THE NEXT CHAPTER
            <br />
            STARTS HERE.
          </div>
        </div>
      </div>
    </section>
  );
}

/**
 * "Same You. A Brighter Tomorrow." — the page's cinematic finale and
 * final conversion moment. Identical content/markup to what previously
 * closed `NeroNextMoveSection` (same NeroFinaleVisual ridge/skyline
 * scene, same copy, same CTAs) — only its position changed: it now
 * renders after For Students / For Consultancies, as the last section
 * before the footer, per the approved landing-page story. No other CTA
 * section follows it.
 */
export function NeroFinaleSection() {
  return (
    <section
      id="pricing"
      className="relative overflow-hidden border-t border-white/10 bg-[#0a0d13]"
    >
      <div className="relative mx-auto max-w-[1536px] px-6 py-16 sm:px-10 sm:py-20 lg:px-20 lg:py-28">
        <div className="relative scroll-mt-24 overflow-hidden rounded-3xl border border-white/10">
          <NeroFinaleVisual />

          <div
            className="pointer-events-none absolute left-5 top-6 z-20 max-w-[170px] -rotate-2 sm:left-8 sm:top-8"
            aria-hidden="true"
          >
            <p className="font-[family-name:var(--font-caveat)] text-xl leading-[1.15] text-app-text/90 sm:text-2xl">
              Same You.
              <br />
              Higher Possibilities.
            </p>
          </div>

          <div
            className="pointer-events-none absolute right-5 top-6 z-20 hidden max-w-[190px] rotate-2 text-right sm:right-8 sm:top-8 sm:block"
            aria-hidden="true"
          >
            <p className="font-[family-name:var(--font-caveat)] text-xl leading-[1.15] text-app-text/90 sm:text-2xl">
              More Opportunities.
              <br />
              A Brighter You.
            </p>
          </div>

          <div className="relative z-10 flex flex-col items-center px-6 pt-20 pb-64 text-center sm:px-10 sm:pt-24 sm:pb-80 lg:py-28 lg:pl-64">
            <div className="flex items-center gap-3">
              <span className="hidden h-px w-10 bg-app-red/50 sm:block" aria-hidden="true" />
              <span className="mono text-[10px] tracking-[0.3em] text-app-red">
                05 / 06 &nbsp; IT&apos;S MORE THAN A JOB.
              </span>
              <span className="hidden h-px w-10 bg-app-red/50 sm:block" aria-hidden="true" />
            </div>

            <h2 className="mt-6 font-[family-name:var(--font-display)] text-[clamp(2.75rem,7vw,5.5rem)] font-bold leading-[1.1] tracking-[-0.03em] text-app-text">
              SAME YOU.
              <br />
              <span className="bg-gradient-to-r from-app-red via-[#ff6a52] to-[#ff9166] bg-clip-text text-transparent">
                A BRIGHTER TOMORROW.
              </span>
            </h2>

            <p className="mx-auto mt-6 max-w-xl text-base leading-7 text-app-muted sm:text-lg">
              Start your next chapter with NERO.
            </p>

            <div className="mt-9 flex flex-col items-center gap-3 sm:flex-row">
              <Link
                href="/register"
                className="app-focus-ring group inline-flex items-center justify-center gap-2 rounded-lg bg-crimson-fill px-7 py-3.5 text-sm font-medium text-white shadow-[0_0_28px_rgba(217,40,31,0.4)] transition hover:bg-crimson-fill-hover"
              >
                Get Started
                <span className="transition-transform group-hover:translate-x-1">
                  →
                </span>
              </Link>

              <Link
                href="/jobs"
                className="app-focus-ring inline-flex items-center justify-center rounded-lg border border-app-border-soft bg-black/20 px-7 py-3.5 text-sm font-medium text-app-text backdrop-blur-sm transition hover:bg-white/10"
              >
                Explore NERO
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function FloatingStat({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-app-border-soft bg-app-panel/90 px-3.5 py-2 shadow-lg backdrop-blur-sm">
      <Icon className="h-3.5 w-3.5 text-app-blue" aria-hidden="true" />
      <span className="mono text-[9px] tracking-[0.12em] text-app-body">
        {label}
      </span>
    </div>
  );
}

function FeatureTile({
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
      className="system-card-reveal flex flex-col items-center gap-3 text-center"
      style={{ animationDelay: `${index * 90}ms` }}
    >
      <div className="flex h-11 w-11 items-center justify-center rounded-full border border-app-border-soft text-app-blue">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </div>
      <div>
        <div className="text-sm font-semibold text-app-text">{title}</div>
        <div className="mt-1 max-w-[150px] text-xs leading-5 text-app-muted">
          {text}
        </div>
      </div>
    </div>
  );
}

function InsightTile({
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
      className="system-card-reveal glass-panel rounded-2xl border border-app-border-soft p-5"
      style={{ animationDelay: `${index * 100}ms` }}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-full border border-app-border-soft text-app-blue">
        <Icon className="h-4 w-4" aria-hidden="true" />
      </div>
      <h4 className="mt-4 text-sm font-semibold text-app-text">{title}</h4>
      <p className="mt-2 text-sm leading-6 text-app-muted">{text}</p>
    </div>
  );
}

function StageTracker() {
  const currentIndex = APPLICATION_STAGES.indexOf(CURRENT_STAGE);

  return (
    <div
      className="flex items-start"
      role="img"
      aria-label={`Application stage: ${CURRENT_STAGE}`}
    >
      {APPLICATION_STAGES.map((stage, index) => {
        const isComplete = index < currentIndex;
        const isCurrent = index === currentIndex;

        return (
          <div key={stage} className="flex flex-1 items-center last:flex-none">
            <div className="flex flex-col items-center gap-2">
              <span
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded-full border text-[10px] font-bold",
                  isCurrent
                    ? "border-app-blue bg-app-blue text-black shadow-[0_0_12px_rgba(10,132,255,0.6)]"
                    : isComplete
                      ? "border-app-success bg-app-success text-black"
                      : "border-app-border-soft bg-app-surface text-app-muted",
                )}
                aria-hidden="true"
              >
                {isComplete ? <Check className="h-3 w-3" /> : index + 1}
              </span>
              <span
                className={cn(
                  "mono text-[9px] tracking-[0.1em]",
                  isCurrent ? "text-app-text" : "text-app-muted/60",
                )}
              >
                {stage.toUpperCase()}
              </span>
            </div>

            {index < APPLICATION_STAGES.length - 1 && (
              <span
                className={cn(
                  "mx-1.5 mb-4 h-px flex-1",
                  isComplete ? "bg-app-success/60" : "bg-app-border-soft",
                )}
                aria-hidden="true"
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function ApplicationInProgressCard() {
  return (
    <div className="system-card-reveal glass-panel relative rounded-2xl border border-app-border-soft p-6 shadow-[0_0_32px_-16px_rgba(10,132,255,0.4)] sm:p-7">
      <span className="absolute right-5 top-5 mono text-[9px] tracking-[0.15em] text-app-faint">
        SAMPLE APPLICATION
      </span>

      <div className="flex items-start gap-4">
        <div
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-app-border-strong bg-app-surface text-sm font-bold text-app-blue"
          aria-hidden="true"
        >
          G
        </div>

        <div className="min-w-0">
          <h4 className="text-lg font-semibold text-app-text">
            AI/ML Engineer
          </h4>
          <p className="mt-0.5 text-sm text-app-muted">Google</p>
          <p className="mt-1 flex items-center gap-1.5 text-xs text-app-faint">
            <MapPin className="h-3 w-3" aria-hidden="true" />
            Mountain View, CA
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Badge tone="neutral-soft">Full-Time</Badge>
        <Badge tone="neutral-soft">Remote</Badge>
        <Badge tone="success-soft" className="ml-auto">
          94% Match*
        </Badge>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {["Python", "LLM", "Machine Learning"].map((skill) => (
          <Badge key={skill} tone="blue-soft">
            {skill}
          </Badge>
        ))}
      </div>

      <div className="mt-6 border-t border-white/10 pt-5">
        <StageTracker />
      </div>

      <div className="mt-5 flex items-start gap-3 rounded-xl border border-app-blue/30 bg-app-blue-soft p-4">
        <Lightbulb
          className="mt-0.5 h-4 w-4 shrink-0 text-app-blue"
          aria-hidden="true"
        />
        <div>
          <p className="mono text-[9px] tracking-[0.15em] text-app-blue">
            NEXT STEP
          </p>
          <p className="mt-1 text-sm leading-6 text-app-body">
            Prepare for your screening call — NERO will help you brush up
            on the skills this role weighs most.
          </p>
        </div>
      </div>
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
