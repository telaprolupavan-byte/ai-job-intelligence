import type { CSSProperties } from "react";
import Link from "next/link";
import {
  Search,
  FileText,
  BarChart3,
  Target,
  Mouse,
  ChevronDown,
  ListChecks,
  FileCheck2,
  Send,
  Settings2,
  Globe,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import NeroBrand from "@/components/app/nero-brand";
import LandingNav from "@/components/app/landing-nav";
import ParallaxController from "@/components/app/parallax-controller";
import NeroHeroVisual from "@/components/app/nero-hero-visual";
import NeroSystemVisual from "@/components/app/nero-system-visual";
import DiscoverJobsSection from "@/components/app/discover-jobs-section";
import NeroJobIntelligenceSection from "@/components/app/nero-job-intelligence-section";
import NeroNextMoveSection, {
  NeroFinaleSection,
} from "@/components/app/nero-next-move-section";
import ProblemSection from "@/components/app/problem-section";
import ResumeIntelligenceSection from "@/components/app/resume-intelligence-section";
import NeroJourneySection from "@/components/app/nero-journey-section";
import StudentSection from "@/components/app/student-section";
import ConsultancySection from "@/components/app/consultancy-section";

const systemBlocks: {
  number: string;
  title: string;
  description: string;
  icon: LucideIcon;
}[] = [
  {
    number: "01",
    title: "DISCOVER",
    description:
      "Search across U.S. opportunities and surface jobs that actually fit your profile.",
    icon: Search,
  },
  {
    number: "02",
    title: "MATCH",
    description:
      "Measure your fit against the role using skills, experience, requirements, and preferences.",
    icon: ListChecks,
  },
  {
    number: "03",
    title: "ATS",
    description:
      "Analyze how ready your resume is for the specific opportunity before you apply.",
    icon: FileCheck2,
  },
  {
    number: "04",
    title: "OPTIMIZE",
    description:
      "Improve your resume truthfully around the requirements that matter most.",
    icon: Settings2,
  },
];

const neroPillars: { icon: LucideIcon; title: string; text: string }[] = [
  {
    icon: FileCheck2,
    title: "Resume Intelligence",
    text: "Understand where your resume stands and what to strengthen.",
  },
  {
    icon: Search,
    title: "Job Intelligence",
    text: "See how a specific opportunity actually lines up with you.",
  },
  {
    icon: Send,
    title: "Application Intelligence",
    text: "Know where every application stands, at every stage.",
  },
];

const featureItems = [
  {
    icon: Search,
    title: "Discover",
    description: "Relevant jobs",
  },
  {
    icon: FileText,
    title: "Match",
    description: "AI-powered insights",
  },
  {
    icon: BarChart3,
    title: "Improve",
    description: "Stronger applications",
  },
  {
    icon: Target,
    title: "Achieve",
    description: "Your career goals",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen overflow-hidden bg-app-bg">
      <ParallaxController />

      {/* Navigation — same links/functionality as before, restyled to
          read as NERO's own instrument bar (mono system-status label,
          crimson hairline) instead of a generic SaaS navbar. */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-app-bg/85 backdrop-blur-md relative">
        <div
          className="hero-hairline pointer-events-none absolute inset-x-0 bottom-0 h-px"
          aria-hidden="true"
        />
        <nav className="relative mx-auto flex h-20 max-w-[1536px] items-center justify-between px-6 sm:px-10 lg:px-20">
          <div className="flex items-center gap-4">
            <NeroBrand imgClassName="h-9 w-auto sm:h-10" sizes="140px" />
            <span className="hidden h-6 w-px bg-white/10 lg:block" aria-hidden="true" />
            <span className="mono hidden text-[9px] tracking-[0.25em] text-app-muted lg:flex lg:items-center lg:gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-app-red shadow-[0_0_8px_rgba(255,59,48,0.6)]" />
              AI JOB INTELLIGENCE
            </span>
          </div>

          <LandingNav />

          <div className="hidden items-center gap-2 lg:flex">
            <Link
              href="/login"
              className="app-focus-ring rounded-lg px-4 py-2 text-sm text-app-body transition hover:text-app-text"
            >
              Sign in
            </Link>

            <Link
              href="/register"
              className="app-focus-ring group inline-flex items-center justify-center gap-2 rounded-lg bg-crimson-fill px-5 py-2.5 text-sm font-medium text-white shadow-[0_0_24px_rgba(217,40,31,0.35)] transition hover:bg-crimson-fill-hover"
            >
              Get started
              <span className="transition-transform group-hover:translate-x-1">
                →
              </span>
            </Link>
          </div>
        </nav>
      </header>

      {/* Hero */}
      <section className="relative">
        <div
          data-parallax-speed="0.04"
          className="technical-grid absolute inset-0 opacity-40"
          aria-hidden="true"
        />
        <div
          data-parallax-speed="0.08"
          className="hero-atmosphere-blue absolute inset-0"
          aria-hidden="true"
        />
        <div
          data-parallax-speed="0.06"
          className="hero-atmosphere-red absolute inset-0"
          aria-hidden="true"
        />

        <div className="pointer-events-none absolute left-0 top-[34%] hidden h-px w-24 bg-gradient-to-r from-app-red/50 to-transparent lg:block" />
        <div className="pointer-events-none absolute left-0 top-[34%] hidden h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-app-red/70 lg:block" />

        <div className="relative mx-auto max-w-[1536px] px-6 pb-10 pt-10 sm:px-10 lg:px-20 lg:pt-14">
          <div className="hero-grid-layout">
            {/* LEFT — copy + CTAs */}
            <div className="hero-area-content flex flex-col justify-center">
              <div
                className="reveal-up flex items-center gap-3"
                style={{ animationDelay: "0ms" }}
              >
                <span className="mono text-[10px] tracking-[0.3em] text-app-red">
                  01 / AI JOB INTELLIGENCE
                </span>
                <span className="h-px w-12 bg-app-red/50" />
              </div>

              <h1
                className="reveal-up mt-5 font-[family-name:var(--font-display)] text-[clamp(2.75rem,6vw,5rem)] font-bold leading-[0.95] tracking-[-0.03em] text-app-text"
                style={{ animationDelay: "80ms" }}
              >
                FIND
                <br />
                BETTER
                <br />
                <span className="bg-gradient-to-r from-[#8fdcff] via-[#5cc6ff] to-app-blue bg-clip-text text-transparent">
                  OPPORTUNITIES.
                </span>
              </h1>

              <p
                className="reveal-up mt-6 max-w-[560px] text-base leading-7 text-app-muted sm:text-lg"
                style={{ animationDelay: "160ms" }}
              >
                Discover relevant jobs, understand your match, analyze ATS
                readiness, and improve your resume before you apply.
              </p>

              <div
                className="reveal-up mt-8 flex flex-col gap-3 sm:flex-row"
                style={{ animationDelay: "220ms" }}
              >
                <Link
                  href="/jobs"
                  className="app-focus-ring group inline-flex items-center justify-center gap-3 rounded-lg bg-crimson-fill px-6 py-3.5 text-sm font-medium text-white shadow-[0_0_28px_rgba(217,40,31,0.4)] transition hover:bg-crimson-fill-hover"
                >
                  Start your search
                  <span className="transition-transform group-hover:translate-x-1">
                    →
                  </span>
                </Link>

                <Link
                  href="#system"
                  className="app-focus-ring inline-flex items-center justify-center rounded-lg border border-app-border-soft bg-white/[0.02] px-6 py-3.5 text-sm font-medium text-app-text transition hover:bg-white/[0.05]"
                >
                  Explore the system
                </Link>
              </div>

              <div
                data-parallax-speed="0.12"
                className="mt-8 border-t border-white/10 pt-5"
              >
                <div
                  className="reveal-up flex items-center gap-3"
                  style={{ animationDelay: "280ms" }}
                >
                  <span className="mono text-[10px] tracking-[0.2em] text-app-muted">
                    SYSTEM STATUS
                  </span>
                  <span className="h-1 w-1 rounded-full bg-app-muted/40" />
                  <span className="flex items-center gap-2 text-xs text-app-body">
                    <span className="h-1.5 w-1.5 rounded-full bg-app-red shadow-[0_0_10px_rgba(255,59,48,0.6)]" />
                    INTELLIGENCE ONLINE
                  </span>
                  <span className="hidden h-1 w-1 rounded-full bg-app-muted/40 sm:block" />
                  <span className="mono hidden text-[10px] tracking-[0.15em] text-app-muted sm:block">
                    DISCOVER / MATCH / ATS / OPTIMIZE
                  </span>
                </div>
              </div>
            </div>

            {/* RIGHT — NERO stage */}
            <div className="hero-area-nero relative flex flex-col items-center pt-4 lg:pt-0">
              <div className="pointer-events-none absolute right-0 top-0 z-20 max-w-[220px] -rotate-2 text-right sm:right-4 sm:top-6">
                <p className="font-[family-name:var(--font-caveat)] text-xl leading-[1.1] text-app-text/90 sm:text-2xl">
                  Better
                  <br />
                  Jobs
                  <br />
                  Ahead!
                </p>
                <svg
                  viewBox="0 0 90 16"
                  className="ml-auto mt-1 h-4 w-20 text-app-red/70"
                  aria-hidden="true"
                >
                  <path
                    d="M2 8c20 8 55 8 76-2"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                  <path
                    d="M68 3l12 3-9 8"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>

              <div
                data-parallax-speed="0.16"
                data-parallax-scale-to="1.04"
                className="w-full pt-14 sm:pt-20 lg:pt-4"
              >
                <NeroHeroVisual />
              </div>

              <div
                data-parallax-speed="0.12"
                className="relative z-20 mx-auto mt-6 max-w-[280px] sm:absolute sm:right-0 sm:top-36 sm:mx-0 sm:mt-0 sm:max-w-[240px] lg:right-2"
              >
                <span className="absolute -left-2.5 top-3 hidden h-4 w-[3px] rounded-full bg-app-red sm:block" />
                <div
                  data-reveal
                  style={{ "--reveal-distance": "16px" } as CSSProperties}
                  className="rounded-xl border border-app-border-soft bg-app-panel/70 px-4 py-3.5 shadow-lg backdrop-blur-sm"
                >
                  <p className="text-xs leading-5 text-app-body">
                    I&apos;ll help you find,
                    <br />
                    match, and prepare
                    <br />
                    for the right opportunities.
                  </p>
                </div>
              </div>
            </div>

            {/* Feature row */}
            <div className="hero-area-features grid grid-cols-2 gap-x-6 gap-y-8 sm:grid-cols-4">
              {featureItems.map((item, index) => (
                <div
                  key={item.title}
                  data-reveal
                  data-reveal-delay={index * 80}
                  className="flex flex-col gap-3"
                >
                  <div className="flex h-11 w-11 items-center justify-center rounded-full border border-app-border-soft text-app-blue">
                    <item.icon className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-app-text">
                      {item.title}
                    </div>
                    <div className="mt-0.5 text-xs text-app-muted">
                      {item.description}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Hero bottom bar */}
        <div className="relative mx-auto flex max-w-[1536px] flex-col items-center gap-4 border-t border-white/5 px-6 py-5 text-center sm:px-10 lg:flex-row lg:justify-between lg:px-20 lg:text-left">
          <div className="flex items-center gap-2.5">
            <span className="hidden h-4 w-[3px] rounded-full bg-app-red/70 lg:block" />
            <div className="mono text-[9px] leading-5 tracking-[0.3em] text-app-muted">
              MORE THAN JOBS
              <br />
              A BRIGHTER YOU
            </div>
          </div>

          <div className="flex flex-col items-center gap-2">
            <span className="mono text-[9px] tracking-[0.3em] text-app-muted">
              SCROLL TO EXPLORE
            </span>
            <Mouse className="h-4 w-4 text-app-muted" aria-hidden="true" />
            <ChevronDown
              className="scroll-dot -mt-1.5 h-3 w-3 text-app-muted"
              aria-hidden="true"
            />
          </div>

          <div className="flex items-center gap-2.5">
            <span className="hidden h-px w-8 bg-gradient-to-r from-transparent to-app-red/50 lg:block" />
            <div className="mono text-[9px] leading-5 tracking-[0.3em] text-app-muted">
              POWERED BY AI
              <br />
              GUIDED BY NERO
            </div>
          </div>
        </div>
      </section>

      {/* The Problem */}
      <ProblemSection />

      {/* Meet NERO / System — one unified NERO introduction: character +
          the three intelligence pillars, immediately followed by the
          underlying four-step system it's built on. */}
      <section
        id="system"
        className="relative overflow-hidden border-t border-white/10 bg-[#090c11]"
      >
        <div className="technical-grid absolute inset-0 opacity-30" aria-hidden="true" />
        <div className="nero-atmosphere absolute inset-0" aria-hidden="true" />
        <div
          className="pointer-events-none absolute -right-32 -top-32 hidden h-[520px] w-[520px] rounded-full border border-white/5 bg-[radial-gradient(circle_at_38%_38%,rgba(10,132,255,0.1),transparent_62%)] lg:block"
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute left-[18%] top-10 hidden h-px w-28 -rotate-[35deg] bg-gradient-to-r from-app-red/70 to-transparent lg:block"
          aria-hidden="true"
        />

        <div className="pointer-events-none absolute right-6 top-8 z-10 hidden items-center gap-2.5 sm:right-10 lg:right-20 lg:flex">
          <span className="h-px w-12 bg-app-red/60" />
          <div className="mono text-right text-[9px] leading-5 tracking-[0.2em] text-app-muted">
            POWERED BY AI
            <br />
            GUIDED BY NERO
          </div>
        </div>

        <div className="relative mx-auto max-w-[1536px] px-6 py-14 sm:px-10 sm:py-18 lg:px-20 lg:py-24">
          {/* Meet NERO — character intro + the three intelligence
              pillars, framed as the overture for the system below
              rather than a second full-scale hero: a smaller display
              size and a tighter approach into the System content keep
              the two halves reading as one continuous scene. */}
          <div className="max-w-2xl">
            <div className="flex items-center gap-3">
              <span className="mono text-[10px] tracking-[0.3em] text-app-red">
                MEET NERO
              </span>
              <span className="h-px w-12 bg-app-red/50" />
            </div>

            <h2 className="mt-4 font-[family-name:var(--font-display)] text-[clamp(2rem,4vw,2.75rem)] font-extrabold leading-[0.95] tracking-[-0.03em] text-app-text">
              MEET{" "}
              <span className="bg-gradient-to-r from-[#8fdcff] via-[#5cc6ff] to-app-blue bg-clip-text text-transparent">
                NERO.
              </span>
            </h2>

            <p className="mt-4 max-w-[520px] text-base leading-7 text-app-muted">
              NERO is your AI job intelligence companion — built to help
              you understand your position, your opportunities, and your
              next move.
            </p>
          </div>

          <div className="mt-8 grid gap-5 sm:grid-cols-3">
            {neroPillars.map((pillar, index) => (
              <div
                key={pillar.title}
                data-reveal
                data-reveal-delay={index * 100}
                className="flex items-start gap-3.5 rounded-xl border border-app-border-soft bg-app-panel/50 p-4"
              >
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-app-blue/50 bg-app-surface/80 text-app-blue">
                  <pillar.icon className="h-4 w-4" aria-hidden="true" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-app-text">
                    {pillar.title}
                  </h3>
                  <p className="mt-1 text-xs leading-5 text-app-muted">
                    {pillar.text}
                  </p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-10 grid gap-10 border-t border-white/5 pt-10 lg:grid-cols-[minmax(0,460px)_1fr] lg:gap-16 xl:grid-cols-[minmax(0,520px)_1fr]">
            {/* LEFT — copy + NERO */}
            <div className="flex flex-col">
              <div className="flex items-center gap-3">
                <span className="mono text-[10px] tracking-[0.3em] text-app-red">
                  02 / THE SYSTEM
                </span>
                <span className="h-px w-12 bg-app-border-strong" />
              </div>

              <h2 className="mt-5 font-[family-name:var(--font-display)] text-[clamp(2.5rem,5vw,3.75rem)] font-extrabold leading-[0.95] tracking-[-0.03em] text-app-text">
                YOUR SEARCH.
                <br />
                <span className="text-app-muted">INTELLIGENTLY.</span>
              </h2>

              <p className="mt-5 max-w-[470px] text-base leading-7 text-app-muted sm:text-lg">
                One workflow for discovering opportunities and understanding
                exactly where you stand before you apply.
              </p>

              <div className="mt-6 flex items-start gap-3">
                <span
                  className="mt-0.5 h-12 w-[3px] shrink-0 rounded-full bg-app-red"
                  aria-hidden="true"
                />
                <div className="mono text-[11px] leading-5 tracking-[0.2em] text-app-body">
                  MORE THAN JOBS
                  <br />
                  A BRIGHTER YOU
                </div>
              </div>

              <div className="relative mt-5 w-fit">
                <p className="font-[family-name:var(--font-caveat)] text-2xl leading-[1.15] text-app-blue sm:text-[26px]">
                  Smarter
                  <br />
                  Search
                  <br />
                  Brighter Future!
                </p>
                <span
                  className="absolute -bottom-1 left-0 h-0.5 w-24 -rotate-6 bg-app-red/80"
                  aria-hidden="true"
                />
              </div>

              <div className="relative mx-auto mt-8 w-full max-w-[280px] sm:max-w-[320px] lg:mt-8 lg:max-w-[360px]">
                <NeroSystemVisual />

                <div
                  className="absolute right-[-8%] top-[6%] z-20 hidden w-[132px] rounded-xl border border-app-blue/50 bg-app-panel/90 p-3 shadow-[0_0_28px_-8px_rgba(10,132,255,0.45)] backdrop-blur-sm sm:block"
                  aria-hidden="true"
                >
                  <Globe className="h-4 w-4 text-app-blue" />
                  <p className="mono mt-2 text-[9px] leading-4 tracking-[0.15em] text-app-body">
                    OPPORTUNITIES
                    <br />
                    NATIONWIDE
                  </p>
                </div>
              </div>
            </div>

            {/* RIGHT — four system blocks + NERO Intelligence Hub */}
            <div>
              {/* Desktop / tablet: 2x2 grid with the hub connecting all four */}
              <div className="system-hub-grid hidden md:grid">
                <SystemCard {...systemBlocks[0]} index={0} className="system-card-1" />
                <SystemConnector orientation="vertical" className="system-line-top h-10 lg:h-12" />
                <SystemCard {...systemBlocks[1]} index={1} className="system-card-2" />

                <SystemConnector orientation="horizontal" className="system-line-left w-10 lg:w-12" />
                <div className="system-hub flex items-center justify-center">
                  <SystemHub />
                </div>
                <SystemConnector orientation="horizontal" className="system-line-right w-10 lg:w-12" />

                <SystemCard {...systemBlocks[2]} index={2} className="system-card-3" />
                <SystemConnector orientation="vertical" className="system-line-bottom h-10 lg:h-12" />
                <SystemCard {...systemBlocks[3]} index={3} className="system-card-4" />
              </div>

              {/* Mobile: single-column stack with a simplified hub divider */}
              <div className="flex flex-col gap-4 md:hidden">
                <SystemCard {...systemBlocks[0]} index={0} />
                <SystemCard {...systemBlocks[1]} index={1} />

                <div className="flex items-center justify-center gap-3 py-1">
                  <span className="h-px max-w-16 flex-1 bg-app-blue/40" aria-hidden="true" />
                  <SystemHub size="sm" />
                  <span className="h-px max-w-16 flex-1 bg-app-blue/40" aria-hidden="true" />
                </div>

                <SystemCard {...systemBlocks[2]} index={2} />
                <SystemCard {...systemBlocks[3]} index={3} />
              </div>
            </div>
          </div>
        </div>

        {/* Bottom utility bar */}
        <div className="relative border-t border-white/5">
          <div className="mx-auto flex max-w-[1536px] flex-col items-center gap-5 px-6 py-6 text-center sm:px-10 lg:flex-row lg:justify-between lg:px-20 lg:text-left">
            <div className="flex items-center gap-3">
              <div
                className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-app-blue/70 bg-app-bg text-sm font-semibold text-app-text"
                aria-hidden="true"
              >
                N
              </div>
              <span className="hidden h-0.5 w-8 bg-app-red sm:block" aria-hidden="true" />
              <div className="mono text-[9px] leading-5 tracking-[0.2em] text-app-muted">
                BUILT FOR
                <br />
                A BRIGHTER TOMORROW
              </div>
              <span className="hidden items-center lg:flex" aria-hidden="true">
                <span className="h-px w-16 bg-gradient-to-r from-app-text/40 to-transparent xl:w-24" />
                <span className="ml-1 text-app-text/70">→</span>
              </span>
            </div>

            <div className="flex flex-col items-center gap-2">
              <span className="mono text-[9px] tracking-[0.3em] text-app-muted">
                SCROLL TO EXPLORE
              </span>
              <Mouse className="h-4 w-4 text-app-muted" aria-hidden="true" />
              <ChevronDown
                className="scroll-dot -mt-1.5 h-3 w-3 text-app-muted"
                aria-hidden="true"
              />
            </div>

            <div className="flex items-center gap-2.5">
              <span className="mono text-[9px] tracking-[0.3em] text-app-muted">
                OPPORTUNITIES AHEAD
              </span>
              <span className="hidden h-px w-10 bg-app-red/60 sm:block" aria-hidden="true" />
            </div>
          </div>
        </div>
      </section>

      {/* Resume Intelligence */}
      <ResumeIntelligenceSection />

      {/* Discover Jobs */}
      <DiscoverJobsSection />

      {/* Job Intelligence (Page 4) */}
      <NeroJobIntelligenceSection />

      {/* The NERO Journey */}
      <NeroJourneySection />

      {/* Make Your Next Move (Page 5) */}
      <NeroNextMoveSection />

      {/* For Students */}
      <StudentSection />

      {/* For Consultancies */}
      <ConsultancySection />

      {/* Final scene — "Same You. A Brighter Tomorrow." — the page's
          cinematic finale and final conversion moment. */}
      <NeroFinaleSection />

      {/* Footer */}
      <footer className="border-t border-white/10">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-6 py-8 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-sm font-semibold">AI JOB INTELLIGENCE</div>
            <div className="mono mt-1 text-[9px] tracking-[0.2em] text-app-muted">
              INTELLIGENCE / MATCH / ATS
            </div>
          </div>

          <div className="mono text-[9px] tracking-[0.15em] text-app-muted">
            SYSTEM / 001
          </div>
        </div>
      </footer>
    </main>
  );
}

function SystemCard({
  number,
  title,
  description,
  icon: Icon,
  index,
  className,
}: {
  number: string;
  title: string;
  description: string;
  icon: LucideIcon;
  index: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "system-card-reveal group relative rounded-2xl border border-app-blue/50 bg-app-panel/70 p-6 shadow-[0_0_28px_-12px_rgba(10,132,255,0.5)] backdrop-blur-[2px] transition hover:border-app-blue/80 hover:bg-app-panel-strong/80 hover:shadow-[0_0_34px_-8px_rgba(10,132,255,0.6)] sm:p-7",
        className,
      )}
      style={{ animationDelay: `${index * 110}ms` }}
    >
      <div className="flex items-center justify-between">
        <span className="mono text-xs text-app-red">{number}</span>
        <span className="h-px w-7 bg-app-body/30" aria-hidden="true" />
      </div>

      <div className="mt-5 flex h-14 w-14 items-center justify-center rounded-xl border border-app-blue/50 bg-app-surface/80 text-app-blue">
        <Icon className="h-6 w-6" aria-hidden="true" />
      </div>

      <h3 className="mt-5 text-lg font-semibold tracking-tight text-app-text sm:text-xl">
        {title}
      </h3>

      <p className="mt-3 text-sm leading-6 text-app-muted">{description}</p>

      <span
        className="pointer-events-none absolute bottom-6 right-6 text-app-text/60 transition group-hover:translate-x-1 group-hover:text-app-red"
        aria-hidden="true"
      >
        →
      </span>
    </div>
  );
}

function SystemConnector({
  orientation,
  className,
}: {
  orientation: "vertical" | "horizontal";
  className?: string;
}) {
  return (
    <div
      className={cn("relative", orientation === "vertical" ? "w-6" : "h-6", className)}
      aria-hidden="true"
    >
      <div
        className={cn(
          "absolute inset-0 m-auto bg-app-blue/40",
          orientation === "vertical" ? "h-full w-px" : "h-px w-full",
        )}
      />
      <span className="absolute left-1/2 top-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-app-red shadow-[0_0_10px_rgba(255,59,48,0.6)]" />
    </div>
  );
}

function SystemHub({ size = "lg" }: { size?: "sm" | "lg" }) {
  const outer =
    size === "lg" ? "h-[104px] w-[104px] lg:h-[120px] lg:w-[120px]" : "h-14 w-14";
  const label = size === "lg" ? "text-3xl lg:text-4xl" : "text-lg";

  return (
    <div
      className={cn(
        "system-hub-pulse relative flex shrink-0 items-center justify-center rounded-full border-2 border-app-blue bg-app-bg/95 shadow-[0_0_36px_-6px_rgba(10,132,255,0.6)]",
        outer,
      )}
      role="img"
      aria-label="NERO Intelligence Hub — the AI layer connecting Discover, Match, ATS, and Optimize"
    >
      <div className="flex h-[74%] w-[74%] items-center justify-center rounded-full border border-app-red bg-app-surface">
        <span
          className={cn(
            "font-[family-name:var(--font-display)] font-bold text-app-text",
            label,
          )}
        >
          N
        </span>
      </div>
    </div>
  );
}
