import type { CSSProperties } from "react";
import Image from "next/image";
import Link from "next/link";
import {
  ClipboardCheck,
  FileText,
  Search,
  Sparkles,
  Target,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import SectionHeading from "@/components/app/section-heading";

const path: { icon: LucideIcon; title: string }[] = [
  { icon: FileText, title: "Resume" },
  { icon: Search, title: "Jobs" },
  { icon: Target, title: "Matches" },
  { icon: Sparkles, title: "Improvements" },
  { icon: ClipboardCheck, title: "Applications" },
  { icon: TrendingUp, title: "Progress" },
];

/**
 * "For Students" — a personal, single-workspace framing, deliberately
 * different in composition from the Consultancy section right after
 * it (one companion figure and one path, not a crowd). NERO stays a
 * companion here, never implying it acts without the student — every
 * stage in the path is something the student reviews and decides on.
 *
 * RESTRAINED motion tier, and a restrained figure to match: NERO's
 * column used to be an uncapped 1fr track, so on a 1440px screen the
 * mascot rendered ~700px tall next to a 3.5rem heading and dwarfed
 * every word of the section. Capped here so the copy stays the
 * subject and NERO stays the companion.
 */
export default function StudentSection() {
  return (
    <section
      id="students"
      className="relative overflow-hidden border-t border-white/10 bg-[#0b0e14]"
    >
      <div className="technical-grid absolute inset-0 opacity-25" aria-hidden="true" />
      <div
        data-parallax-speed="0.08"
        data-parallax-local
        className="student-atmosphere absolute inset-0"
        aria-hidden="true"
      />

      <div className="landing-shell landing-band">
        <div className="grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,360px)] lg:items-center lg:gap-16">
          <div>
            <SectionHeading
              eyebrow="FOR STUDENTS"
              title={
                <>
                  BUILT AROUND{" "}
                  <span className="bg-gradient-to-r from-[#8fdcff] via-[#5cc6ff] to-app-blue bg-clip-text text-transparent">
                    YOUR CAREER.
                  </span>
                </>
              }
              lede="Your resume. Your opportunities. Your decisions. Your progress."
            />

            <div className="stack-md grid grid-cols-3 gap-x-4 gap-y-6 sm:flex sm:flex-wrap sm:gap-6">
              {path.map((step, index) => (
                <div
                  key={step.title}
                  data-reveal
                  data-reveal-delay={index * 80}
                  className="flex flex-col items-center gap-2.5 text-center sm:w-[88px]"
                >
                  <div className="flex h-11 w-11 items-center justify-center rounded-full border border-app-border-soft text-app-blue">
                    <step.icon className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <span className="mono text-[9px] leading-4 tracking-[0.15em] text-app-muted">
                    {step.title.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>

            <p data-reveal className="nero-note stack-md max-w-md text-app-blue">
              You review it. You decide. NERO just makes it clearer.
            </p>

            <div className="stack-md">
              <Link
                href="/register"
                className="app-focus-ring group inline-flex items-center justify-center gap-2 rounded-lg bg-crimson-fill px-6 py-3.5 text-sm font-medium text-white shadow-[0_0_28px_rgba(217,40,31,0.4)] transition hover:bg-crimson-fill-hover"
              >
                Explore NERO for Students
                <span className="transition-transform group-hover:translate-x-1">
                  →
                </span>
              </Link>
            </div>
          </div>

          <div
            data-parallax-speed="0.08"
            data-parallax-scale-to="1.03"
            data-parallax-local
            className="relative mx-auto w-full max-w-[260px] sm:max-w-[300px] lg:max-w-[340px]"
          >
            {/* Encouraging beat: the thumbs-up in this pose is doing the
                work here, so the size stays as approved and only the
                cadence changes — 5.6s / 16px against the 6s / 14px
                default, a little livelier and warmer than the sections
                either side of it. */}
            <Image
              src="/brand/nero-hero-figure.png"
              alt="NERO, the AI Job Intelligence mascot, giving a student a thumbs up alongside their own workspace"
              width={1098}
              height={1334}
              sizes="(min-width: 1024px) 340px, (min-width: 640px) 300px, 260px"
              quality={95}
              style={
                {
                  "--nero-float-duration": "5.6s",
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
        </div>
      </div>
    </section>
  );
}
