import type { CSSProperties } from "react";
import Link from "next/link";
import {
  Search,
  FileText,
  BarChart3,
  Target,
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
import ScrollCue from "@/components/app/scroll-cue";
import SectionHeading from "@/components/app/section-heading";
import NeroHeroVisual from "@/components/app/nero-hero-visual";
import NeroSystemVisual from "@/components/app/nero-system-visual";
import DiscoverJobsSection from "@/components/app/discover-jobs-section";
import NeroJobIntelligenceSection from "@/components/app/nero-job-intelligence-section";
import NeroFinaleSection from "@/components/app/nero-finale-section";
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
    <main className="min-h-screen overflow-x-clip bg-app-bg">
      <ParallaxController />

      {/* Navigation — same links/functionality as before, restyled to
          read as NERO's own instrument bar (mono system-status label,
          crimson hairline) instead of a generic SaaS navbar. */}
      {/* data-scroll-progress-page: the header is the only consumer of
          page-level scroll progress, so the controller writes the
          variable here instead of on :root — see the note in
          globals.css for why that distinction is worth ~100ms a frame. */}
      <header
        data-scroll-progress-page
        className="site-header sticky top-0 z-50 border-b border-white/5 bg-app-bg/85 backdrop-blur-md relative"
      >
        <div
          className="hero-hairline pointer-events-none absolute inset-x-0 bottom-0 h-px"
          aria-hidden="true"
        />
        <nav className="landing-shell flex h-20 items-center justify-between">
          <div className="flex items-center gap-4">
            <NeroBrand imgClassName="h-12 w-auto sm:h-14" sizes="200px" />
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

      {/* Hero — the page's one STRONG cinematic identity moment. Sized
          to own the fold (min-height tied to the viewport minus the
          header) instead of being driven purely by copy length, so the
          first screen reads as a composed scene rather than a block of
          text that happens to be at the top. */}
      <section className="relative overflow-hidden">
        <div
          data-parallax-speed="0.05"
          className="technical-grid absolute inset-0 opacity-40"
          aria-hidden="true"
        />
        <div
          data-parallax-speed="0.16"
          className="hero-atmosphere-blue absolute inset-0"
          aria-hidden="true"
        />
        <div
          data-parallax-speed="0.11"
          className="hero-atmosphere-red absolute inset-0"
          aria-hidden="true"
        />

        <div
          data-parallax-speed="0.09"
          className="pointer-events-none absolute left-0 top-[34%] hidden h-px w-24 bg-gradient-to-r from-app-red/50 to-transparent lg:block"
        />
        <div
          data-parallax-speed="0.09"
          className="pointer-events-none absolute left-0 top-[34%] hidden h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-app-red/70 lg:block"
        />

        <div className="landing-shell flex flex-col justify-center pb-12 pt-8 sm:pt-10 lg:min-h-[calc(100svh-13rem)] lg:pb-10 lg:pt-6">
          <div className="hero-grid-layout">
            {/* LEFT — copy + CTAs. Parallax goes on this wrapper (not on
                the reveal-up children directly) — a CSS @keyframes
                animation's fill-forwards value always wins over a JS
                inline transform on the same element, so it has to sit
                one level up from anything carrying reveal-up/nero-float/
                system-card-reveal. Very small speed by design: a
                near-fixed depth anchor, the slowest-moving readable
                layer in the scene, so the atmosphere/NERO drifting past
                it behind and beside it reads as depth rather than the
                whole hero panning. */}
            <div
              data-parallax-speed="0.02"
              className="hero-area-content flex flex-col justify-center"
            >
              <div
                className="reveal-up flex items-center gap-3"
                style={{ animationDelay: "0ms" }}
              >
                <span className="mono text-[10px] tracking-[0.3em] text-app-red">
                  AI JOB INTELLIGENCE
                </span>
                <span className="h-px w-12 bg-app-red/50" />
              </div>

              <h1
                className="display-hero reveal-up mt-5"
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
                className="section-lede reveal-up mt-6"
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
                  className="reveal-up flex flex-wrap items-center gap-x-3 gap-y-2"
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

            {/* RIGHT — NERO stage. The figure is capped and centered in
                its own column rather than sized off the raw grid track:
                at 1440+ it used to run all the way to the viewport edge
                while every line of text respected a 64px gutter, which
                is what made the hero feel like two unrelated halves. */}
            <div className="hero-area-nero relative flex items-center justify-center">
              <div className="relative w-full max-w-[440px]">
                <div
                  data-parallax-speed="0.2"
                  data-parallax-x="0.015"
                  className="pointer-events-none absolute right-0 top-1 z-20 max-w-[132px] -rotate-2 text-right"
                >
                  <p className="nero-note text-app-text/90">
                    Better
                    <br />
                    Jobs
                    <br />
                    Ahead!
                  </p>
                  <svg
                    viewBox="0 0 90 16"
                    className="ml-auto mt-1 h-4 w-16 text-app-red/70"
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
                  data-parallax-speed="0.22"
                  data-parallax-scale-to="1.06"
                  className="w-full px-8 pt-14 sm:px-10 sm:pt-16 lg:px-0 lg:pt-6"
                >
                  <NeroHeroVisual priority />
                </div>

                <div
                  data-parallax-speed="0.18"
                  className="relative z-20 mx-auto mt-4 max-w-[280px] sm:absolute sm:right-[-11%] sm:top-[24%] sm:mx-0 sm:mt-0 sm:max-w-[208px]"
                >
                  <span className="absolute -left-2.5 top-3 hidden h-4 w-[3px] rounded-full bg-app-red sm:block" />
                  <div
                    data-reveal
                    style={{ "--reveal-distance": "16px" } as CSSProperties}
                    className="rounded-xl border border-app-border-soft bg-app-panel/80 px-4 py-3.5 shadow-lg backdrop-blur-sm"
                  >
                    <p className="font-[family-name:var(--font-instrument-sans)] text-xs leading-5 text-app-body">
                      I&apos;ll help you find, match, and prepare for the
                      right opportunities.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Feature row */}
            <div className="hero-area-features grid grid-cols-2 gap-x-6 gap-y-7 sm:grid-cols-4">
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

        {/* Hero bottom bar — the page's only scroll cue. The same
            mouse/chevron pair used to repeat at the foot of four
            different sections, which is most of what made the page read
            as a template rather than one composition. */}
        <div className="relative border-t border-white/5">
          <div className="landing-shell flex flex-col items-center gap-4 py-5 text-center sm:flex-row sm:justify-between sm:text-left">
            <div className="flex items-center gap-2.5">
              <span className="hidden h-4 w-[3px] rounded-full bg-app-red/70 sm:block" />
              <div className="mono text-[9px] leading-5 tracking-[0.3em] text-app-muted">
                MORE THAN JOBS
                <br />
                A BRIGHTER YOU
              </div>
            </div>

            <ScrollCue label="SCROLL TO EXPLORE" className="order-last sm:order-none" />

            <div className="flex items-center gap-2.5">
              <span className="hidden h-px w-8 bg-gradient-to-r from-transparent to-app-red/50 sm:block" />
              <div className="mono text-[9px] leading-5 tracking-[0.3em] text-app-muted sm:text-right">
                POWERED BY AI
                <br />
                GUIDED BY NERO
              </div>
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
        {/* MEDIUM tier: atmosphere + decorative ring get local parallax,
            consistent with the rest of the page's atmosphere layers
            (Hero's is the one exception, by design). The ring carries
            more of the section's depth budget than the atmosphere wash
            so NERO reads as the clear focal point between the two. */}
        <div
          data-parallax-speed="0.06"
          data-parallax-local
          className="nero-atmosphere absolute inset-0"
          aria-hidden="true"
        />
        <div
          data-parallax-speed="0.12"
          data-parallax-local
          className="pointer-events-none absolute -right-40 -top-32 hidden h-[520px] w-[520px] rounded-full border border-white/5 bg-[radial-gradient(circle_at_38%_38%,rgba(10,132,255,0.1),transparent_62%)] lg:block"
          aria-hidden="true"
        />
        <div
          data-parallax-speed="0.16"
          data-parallax-local
          className="pointer-events-none absolute left-[18%] top-10 hidden h-px w-28 -rotate-[35deg] bg-gradient-to-r from-app-red/70 to-transparent lg:block"
          aria-hidden="true"
        />

        <div className="landing-shell landing-band-tight">
          {/* Meet NERO — character intro + the three intelligence
              pillars, framed as the overture for the system below
              rather than a second full-scale hero: a smaller display
              size and a tighter approach into the System content keep
              the two halves reading as one continuous scene. */}
          <SectionHeading
            eyebrow="MEET NERO"
            size="sub"
            title={
              <>
                MEET{" "}
                <span className="bg-gradient-to-r from-[#8fdcff] via-[#5cc6ff] to-app-blue bg-clip-text text-transparent">
                  NERO.
                </span>
              </>
            }
            lede="NERO is your AI job intelligence companion — built to help you understand your position, your opportunities, and your next move."
          />

          <div className="stack-md grid grid-cols-1 gap-3 sm:grid-cols-3 sm:gap-4">
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

          <div className="stack-md border-t border-white/5 pt-[var(--stack-md)]">
            {/* The System's own header runs the full measure. It used
                to live inside the left column, where "INTELLIGENTLY."
                — the single widest word on the page — was 230px wider
                than the track holding it, which is what blew the whole
                section past the viewport on a phone. */}
            <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between lg:gap-12">
              <SectionHeading
                eyebrow="THE SYSTEM"
                title={
                  <>
                    YOUR SEARCH.
                    <br />
                    <span className="text-app-muted">INTELLIGENTLY.</span>
                  </>
                }
                className="max-w-2xl"
              />

              <p className="section-lede lg:pb-2">
                One workflow for discovering opportunities and
                understanding exactly where you stand before you apply.
              </p>
            </div>

            <div className="stack-md grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,0.68fr)_minmax(0,1fr)] lg:items-center lg:gap-10">
            {/* LEFT — supporting lines + NERO */}
            <div className="flex flex-col">
              {/* Brand line + handwritten note share one row so the
                  column doesn't grow into a single tall ribbon of
                  stacked one-liners above the figure. */}
              <div className="flex flex-wrap items-start gap-x-10 gap-y-6">
                <div className="flex items-start gap-3">
                  <span
                    className="mt-0.5 h-11 w-[3px] shrink-0 rounded-full bg-app-red"
                    aria-hidden="true"
                  />
                  <div className="mono text-[11px] leading-5 tracking-[0.2em] text-app-body">
                    MORE THAN JOBS
                    <br />
                    A BRIGHTER YOU
                  </div>
                </div>

                <div className="relative w-fit">
                  <p className="nero-note text-app-blue">
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
              </div>

              <div
                data-parallax-speed="0.1"
                data-parallax-scale-to="1.04"
                data-parallax-local
                className="stack-md relative mx-auto w-full max-w-[300px] sm:max-w-[360px] lg:mx-0 lg:max-w-[400px]"
              >
                <NeroSystemVisual />

                <div
                  data-parallax-speed="0.05"
                  data-parallax-local
                  className="absolute right-[-20%] top-[62%] z-20 hidden w-[124px] rounded-xl border border-app-blue/50 bg-app-panel/90 p-3 shadow-[0_0_28px_-8px_rgba(10,132,255,0.45)] backdrop-blur-sm sm:block"
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
                <SystemCard {...systemBlocks[1]} index={1} className="system-card-2" />

                {/* One cross of spokes drawn from the hub out to the
                    four cards, instead of four separate connector
                    elements sitting in their own grid tracks: those
                    stopped short of both the hub and the cards, so the
                    "system" read as four unconnected tiles around a
                    disc. */}
                <div className="system-hub relative flex items-center justify-center">
                  <div className="system-spokes" aria-hidden="true">
                    <span className="system-spoke-x" />
                    <span className="system-spoke-y" />
                    <span className="system-node system-node-t" />
                    <span className="system-node system-node-b" />
                    <span className="system-node system-node-l" />
                    <span className="system-node system-node-r" />
                  </div>
                  <SystemHub />
                </div>

                <SystemCard {...systemBlocks[2]} index={2} className="system-card-3" />
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
        </div>

        {/* Bottom utility rail — quieter than before and without the
            duplicate scroll cue; it now only carries the brand line
            that bridges into Resume Intelligence. */}
        <div className="relative border-t border-white/5">
          <div className="landing-shell flex flex-col items-center gap-4 py-5 text-center sm:flex-row sm:justify-between sm:text-left">
            <div className="flex items-center gap-3">
              <div
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-app-blue/70 bg-app-bg text-sm font-semibold text-app-text"
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

      {/* For Students */}
      <StudentSection />

      {/* For Consultancies */}
      <ConsultancySection />

      {/* Final scene — "Same You. A Brighter Tomorrow." — the page's
          cinematic finale and final conversion moment. */}
      <NeroFinaleSection />

      {/* Footer */}
      <footer className="border-t border-white/10 bg-[#080a10]">
        <div className="landing-shell flex flex-col gap-6 py-10 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <NeroBrand imgClassName="h-8 w-auto" sizes="120px" preload={false} />
            <span className="hidden h-8 w-px bg-white/10 sm:block" aria-hidden="true" />
            <div>
              <div className="text-sm font-semibold text-app-text">
                AI JOB INTELLIGENCE
              </div>
              <div className="mono mt-1 text-[9px] tracking-[0.2em] text-app-muted">
                INTELLIGENCE / MATCH / ATS
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <Link
              href="/login"
              className="app-focus-ring text-sm text-app-body transition hover:text-app-text"
            >
              Sign in
            </Link>
            <span className="h-4 w-px bg-white/10" aria-hidden="true" />
            <Link
              href="/register"
              className="app-focus-ring text-sm text-app-body transition hover:text-app-text"
            >
              Get started
            </Link>
            <span className="hidden h-4 w-px bg-white/10 sm:block" aria-hidden="true" />
            <div className="mono hidden text-[9px] tracking-[0.15em] text-app-muted sm:block">
              SYSTEM / 001
            </div>
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
      data-reveal
      data-reveal-delay={index * 90}
      style={{ "--reveal-distance": "18px" } as CSSProperties}
      className={cn(
        "group relative flex h-full flex-col rounded-2xl border border-app-blue/40 bg-app-panel/70 p-5 shadow-[0_0_28px_-14px_rgba(10,132,255,0.5)] transition hover:border-app-blue/80 hover:bg-app-panel-strong/80 hover:shadow-[0_0_34px_-8px_rgba(10,132,255,0.6)]",
        className,
      )}
    >
      <div className="flex items-center justify-between">
        <span className="mono text-xs text-app-red">{number}</span>
        <span className="h-px w-7 bg-app-body/30" aria-hidden="true" />
      </div>

      <div className="mt-4 flex h-11 w-11 items-center justify-center rounded-xl border border-app-blue/50 bg-app-surface/80 text-app-blue">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </div>

      <h3 className="mt-3 text-base font-semibold tracking-tight text-app-text sm:text-lg">
        {title}
      </h3>

      <p className="mt-2 text-sm leading-6 text-app-muted">{description}</p>

      <span
        className="mt-auto pt-3 text-app-text/60 transition group-hover:translate-x-1 group-hover:text-app-red"
        aria-hidden="true"
      >
        →
      </span>
    </div>
  );
}

function SystemHub({ size = "lg" }: { size?: "sm" | "lg" }) {
  const outer =
    size === "lg" ? "h-20 w-20 lg:h-24 lg:w-24" : "h-14 w-14";
  const label = size === "lg" ? "text-2xl lg:text-[28px]" : "text-lg";

  return (
    <div
      className={cn(
        "system-hub-pulse relative z-10 flex shrink-0 items-center justify-center rounded-full border-2 border-app-blue bg-app-bg shadow-[0_0_36px_-6px_rgba(10,132,255,0.6)]",
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
