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
 */
export default function StudentSection() {
  return (
    <section
      id="students"
      className="relative overflow-hidden border-t border-white/10 bg-[#0b0e14]"
    >
      <div className="technical-grid absolute inset-0 opacity-25" aria-hidden="true" />
      <div
        data-parallax-speed="0.06"
        data-parallax-local
        className="student-atmosphere absolute inset-0"
        aria-hidden="true"
      />

      <div className="relative mx-auto max-w-[1536px] px-6 py-20 sm:px-10 sm:py-24 lg:px-20 lg:py-28">
        <div className="grid gap-14 lg:grid-cols-[minmax(0,620px)_1fr] lg:items-center lg:gap-16">
          <div>
            <div className="flex items-center gap-3">
              <span className="mono text-[10px] tracking-[0.3em] text-app-red">
                FOR STUDENTS
              </span>
              <span className="h-px w-12 bg-app-red/50" />
            </div>

            <h2 className="mt-5 font-[family-name:var(--font-display)] text-[clamp(2.5rem,5.5vw,4rem)] font-extrabold leading-[0.95] tracking-[-0.03em] text-app-text">
              BUILT AROUND{" "}
              <span className="bg-gradient-to-r from-[#8fdcff] via-[#5cc6ff] to-app-blue bg-clip-text text-transparent">
                YOUR CAREER.
              </span>
            </h2>

            <p className="mt-6 max-w-[520px] text-base leading-7 text-app-muted sm:text-lg">
              Your resume. Your opportunities. Your decisions. Your
              progress.
            </p>

            <div className="mt-12 flex flex-wrap gap-4 sm:gap-5">
              {path.map((step, index) => (
                <div
                  key={step.title}
                  data-reveal
                  data-reveal-delay={index * 80}
                  className="flex flex-col items-center gap-2.5 text-center"
                >
                  <div className="flex h-11 w-11 items-center justify-center rounded-full border border-app-border-soft text-app-blue">
                    <step.icon className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <span className="mono text-[9px] tracking-[0.15em] text-app-muted">
                    {step.title.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>

            <p
              data-reveal
              className="mt-10 max-w-md font-[family-name:var(--font-caveat)] text-2xl leading-[1.2] text-app-blue sm:text-[26px]"
            >
              You review it. You decide. NERO just makes it clearer.
            </p>

            <div className="mt-10">
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
            data-parallax-local
            className="relative mx-auto w-full max-w-[300px] lg:max-w-none"
          >
            <Image
              src="/brand/nero-hero-figure.png"
              alt="NERO, the AI Job Intelligence mascot, alongside a student's own workspace"
              width={1098}
              height={1334}
              sizes="(min-width: 1024px) 320px, (min-width: 640px) 280px, 220px"
              quality={95}
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
