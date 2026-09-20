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
  Settings2,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import NeroBrand from "@/components/app/nero-brand";
import LandingNav from "@/components/app/landing-nav";
import NeroHeroVisual from "@/components/app/nero-hero-visual";
import NeroSystemVisual from "@/components/app/nero-system-visual";

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
      {/* Navigation */}
      <header className="relative z-50 border-b border-white/10 bg-app-bg/80 backdrop-blur-md">
        <nav className="relative mx-auto flex h-[90px] max-w-[1536px] items-center justify-between px-6 sm:px-10 lg:px-20">
          <NeroBrand imgClassName="h-11 w-auto sm:h-12" sizes="160px" />

          <LandingNav />

          <div className="hidden items-center gap-3 lg:flex">
            <Link
              href="/login"
              className="app-focus-ring px-4 py-2 text-sm text-app-body transition hover:text-app-text"
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
        <div className="technical-grid absolute inset-0 opacity-40" />
        <div className="nero-atmosphere absolute inset-0" />

        <div className="pointer-events-none absolute left-0 top-[34%] hidden h-px w-24 bg-gradient-to-r from-app-red/50 to-transparent lg:block" />
        <div className="pointer-events-none absolute left-0 top-[34%] hidden h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-app-red/70 lg:block" />

        <div className="relative mx-auto max-w-[1536px] px-6 pb-10 pt-10 sm:px-10 lg:px-20 lg:pt-14">
          <div className="hero-grid-layout">
            {/* LEFT — copy + CTAs */}
            <div className="hero-area-content flex flex-col justify-center">
              <div className="flex items-center gap-3">
                <span className="mono text-[10px] tracking-[0.3em] text-app-red">
                  01 / AI JOB INTELLIGENCE
                </span>
                <span className="h-px w-12 bg-app-red/50" />
              </div>

              <h1 className="mt-5 font-[family-name:var(--font-display)] text-[clamp(2.75rem,6vw,5rem)] font-bold leading-[0.95] tracking-[-0.03em] text-app-text">
                FIND
                <br />
                BETTER
                <br />
                <span className="bg-gradient-to-r from-[#8fdcff] via-[#5cc6ff] to-app-blue bg-clip-text text-transparent">
                  OPPORTUNITIES.
                </span>
              </h1>

              <p className="mt-6 max-w-[560px] text-base leading-7 text-app-muted sm:text-lg">
                Discover relevant jobs, understand your match, analyze ATS
                readiness, and improve your resume before you apply.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
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

              <div className="mt-8 flex items-center gap-3 border-t border-white/10 pt-5">
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

              <div className="w-full pt-14 sm:pt-20 lg:pt-4">
                <NeroHeroVisual />
              </div>

              <div className="relative z-20 mx-auto mt-6 max-w-[280px] sm:absolute sm:right-0 sm:top-36 sm:mx-0 sm:mt-0 sm:max-w-[240px] lg:right-2">
                <span className="absolute -left-2.5 top-3 hidden h-4 w-[3px] rounded-full bg-app-red sm:block" />
                <div className="rounded-xl border border-app-border-soft bg-app-panel/70 px-4 py-3.5 shadow-lg backdrop-blur-sm">
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
              {featureItems.map((item) => (
                <div key={item.title} className="flex flex-col gap-3">
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

      {/* System */}
      <section
        id="system"
        className="relative overflow-hidden border-t border-white/10 bg-[#090c11]"
      >
        <div className="technical-grid absolute inset-0 opacity-30" aria-hidden="true" />
        <div className="nero-atmosphere absolute inset-0" aria-hidden="true" />

        <div className="pointer-events-none absolute right-6 top-8 z-10 hidden items-center gap-2.5 sm:right-10 lg:right-20 lg:flex">
          <span className="h-px w-12 bg-app-red/60" />
          <div className="mono text-right text-[9px] leading-5 tracking-[0.2em] text-app-muted">
            POWERED BY AI
            <br />
            GUIDED BY NERO
          </div>
        </div>

        <div className="relative mx-auto max-w-[1536px] px-6 py-16 sm:px-10 sm:py-20 lg:px-20 lg:py-28">
          <div className="grid gap-14 lg:grid-cols-[minmax(0,460px)_1fr] lg:gap-16 xl:grid-cols-[minmax(0,520px)_1fr]">
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

              <p className="mt-6 max-w-[470px] text-base leading-7 text-app-muted sm:text-lg">
                One workflow for discovering opportunities and understanding
                exactly where you stand before you apply.
              </p>

              <div className="mt-8 flex items-start gap-3">
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

              <div className="relative mt-6 w-fit">
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

              <div className="mt-10 lg:mt-12">
                <NeroSystemVisual />
              </div>
            </div>

            {/* RIGHT — four system blocks + NERO Intelligence Hub */}
            <div>
              {/* Desktop / tablet: 2x2 grid with the hub connecting all four */}
              <div className="system-hub-grid hidden md:grid">
                <SystemCard {...systemBlocks[0]} index={0} className="system-card-1" />
                <div
                  className="system-line-top h-10 w-px bg-app-blue/40 lg:h-12"
                  aria-hidden="true"
                />
                <SystemCard {...systemBlocks[1]} index={1} className="system-card-2" />

                <div
                  className="system-line-left h-px w-10 bg-app-blue/40 lg:w-12"
                  aria-hidden="true"
                />
                <div className="system-hub flex items-center justify-center">
                  <SystemHub />
                </div>
                <div
                  className="system-line-right h-px w-10 bg-app-blue/40 lg:w-12"
                  aria-hidden="true"
                />

                <SystemCard {...systemBlocks[2]} index={2} className="system-card-3" />
                <div
                  className="system-line-bottom h-10 w-px bg-app-blue/40 lg:h-12"
                  aria-hidden="true"
                />
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
              <span
                className="hidden text-app-text/70 lg:inline-block"
                aria-hidden="true"
              >
                →
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

      {/* Match intelligence */}
      <section id="how-it-works" className="relative border-t border-white/10">
        <div className="technical-grid absolute inset-0 opacity-30" />

        <div className="relative mx-auto max-w-7xl px-6 py-24 lg:px-8 lg:py-32">
          <div className="mb-14">
            <div className="mono text-[10px] tracking-[0.3em] text-app-red">
              03 / MATCH INTELLIGENCE
            </div>

            <h2 className="font-[family-name:var(--font-display)] mt-5 max-w-3xl text-4xl font-semibold tracking-[-0.04em] sm:text-6xl">
              NOT EVERY JOB
              <br />
              <span className="text-app-muted">
                DESERVES YOUR TIME.
              </span>
            </h2>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <Metric
              value="94%"
              label="JOB MATCH"
              description="How closely your profile aligns with the opportunity."
            />

            <Metric
              value="91%"
              label="ATS READINESS"
              description="How effectively your resume addresses the specific role."
            />

            <Metric
              value="HIGH"
              label="APPLICATION SIGNAL"
              description="A combined view of relevance, readiness, and priority."
            />
          </div>
        </div>
      </section>

      {/* Philosophy */}
      <section id="resources" className="border-t border-white/10">
        <div className="mx-auto max-w-7xl px-6 py-24 lg:px-8 lg:py-32">
          <div className="grid gap-16 lg:grid-cols-2">
            <div>
              <div className="mono text-[10px] tracking-[0.3em] text-app-red">
                04 / PRINCIPLES
              </div>

              <h2 className="font-[family-name:var(--font-display)] mt-5 text-4xl font-semibold tracking-[-0.04em] sm:text-5xl">
                INTELLIGENCE
                <br />
                <span className="text-app-muted">WITHOUT NOISE.</span>
              </h2>
            </div>

            <div className="space-y-8">
              <Principle
                number="01"
                title="PERSONAL"
                text="Your resume, experience, skills, titles, and preferences shape the search."
              />

              <Principle
                number="02"
                title="TRUTHFUL"
                text="Recommendations improve your existing qualifications without fabricating experience."
              />

              <Principle
                number="03"
                title="TRANSPARENT"
                text="Every match and recommendation should have a reason behind it."
              />

              <Principle
                number="04"
                title="USER CONTROLLED"
                text="The system helps you decide. It does not blindly apply to jobs for you."
              />
            </div>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section id="pricing" className="border-t border-white/10">
        <div className="relative overflow-hidden">
          <div className="red-atmosphere absolute inset-0" />

          <div className="relative mx-auto max-w-5xl px-6 py-28 text-center lg:px-8 lg:py-40">
            <div className="mono text-[10px] tracking-[0.3em] text-app-red">
              05 / BEGIN
            </div>

            <h2 className="font-[family-name:var(--font-display)] mt-6 text-5xl font-semibold tracking-[-0.05em] sm:text-7xl">
              READY TO
              <br />
              <span className="text-app-muted">FIND YOUR EDGE?</span>
            </h2>

            <p className="mx-auto mt-6 max-w-xl text-app-muted">
              Upload your resume. Define your target. Let the intelligence
              layer handle the search.
            </p>

            <Link
              href="/register"
              className="mt-9 inline-flex rounded-lg bg-crimson-fill px-7 py-3.5 text-sm font-medium text-white transition hover:bg-crimson-fill-hover"
            >
              Create your account
            </Link>
          </div>
        </div>
      </section>

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
        "system-card-reveal group relative rounded-2xl border border-app-blue/40 bg-app-panel/70 p-6 backdrop-blur-[2px] transition hover:border-app-blue/70 hover:bg-app-panel-strong/80 sm:p-7",
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

function SystemHub({ size = "lg" }: { size?: "sm" | "lg" }) {
  const outer =
    size === "lg" ? "h-[104px] w-[104px] lg:h-[120px] lg:w-[120px]" : "h-14 w-14";
  const label = size === "lg" ? "text-3xl lg:text-4xl" : "text-lg";

  return (
    <div
      className={cn(
        "system-hub-pulse blue-glow relative flex shrink-0 items-center justify-center rounded-full border-2 border-app-blue/80 bg-app-bg/95",
        outer,
      )}
      role="img"
      aria-label="NERO Intelligence Hub — the AI layer connecting Discover, Match, ATS, and Optimize"
    >
      <div className="flex h-[74%] w-[74%] items-center justify-center rounded-full border border-app-red/70 bg-app-surface">
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

function Metric({
  value,
  label,
  description,
}: {
  value: string;
  label: string;
  description: string;
}) {
  return (
    <div className="red-glow rounded-xl border border-white/10 bg-app-panel p-7">
      <div className="text-4xl font-semibold tracking-[-0.04em] text-app-red">
        {value}
      </div>

      <div className="mono mt-4 text-[10px] tracking-[0.2em]">
        {label}
      </div>

      <p className="mt-4 text-sm leading-6 text-app-muted">
        {description}
      </p>
    </div>
  );
}

function Principle({
  number,
  title,
  text,
}: {
  number: string;
  title: string;
  text: string;
}) {
  return (
    <div className="flex gap-6 border-b border-white/10 pb-8">
      <div className="mono pt-1 text-[10px] text-app-red">{number}</div>

      <div>
        <h3 className="text-sm font-semibold tracking-wide">{title}</h3>
        <p className="mt-2 max-w-lg text-sm leading-6 text-app-muted">
          {text}
        </p>
      </div>
    </div>
  );
}
