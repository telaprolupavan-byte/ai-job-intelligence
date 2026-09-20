import type { CSSProperties } from "react";
import Link from "next/link";
import { AlertTriangle, Eye, Lock, Users, type LucideIcon } from "lucide-react";

// Deterministic per-dot offsets (not random per render) so each dot's
// "settle" reveal is stable across renders — the illusion of many
// individuals coming into a structured view depends on each dot
// resolving to exactly the same tidy grid position every time.
const STUDENT_DOTS = Array.from({ length: 24 }, (_, i) => {
  const rotate = ((i * 37) % 17) - 8;
  const delay = (i % 8) * 60;
  const state = i % 5 === 0 ? "attention" : i % 3 === 0 ? "progress" : "neutral";
  return { id: i, rotate, delay, state };
});

const STATE_CLASS: Record<string, string> = {
  neutral: "border-app-border-soft bg-app-panel/70 text-app-muted",
  progress: "border-app-blue/50 bg-app-blue-soft text-app-blue",
  attention: "border-app-amber/50 bg-app-amber-soft text-app-amber",
};

const sequence: { icon: LucideIcon; title: string }[] = [
  { icon: Users, title: "Many Students" },
  { icon: Eye, title: "Structured Visibility" },
  { icon: AlertTriangle, title: "Attention Areas" },
];

/**
 * "For Consultancies" — deliberately different in composition from
 * the Student section before it: many small entities (a grid of
 * anonymous placeholder dots, no names, no real data) rather than one
 * companion figure, so the parallax itself communicates scale. Dots
 * carry only an illustrative status color (neutral / in-progress /
 * needs-attention) — never real student data — and settle from a
 * scattered tilt into a clean grid as they're scrolled into view,
 * standing in for "many students organizing into a structured view."
 */
export default function ConsultancySection() {
  return (
    <section
      id="consultancy"
      className="relative overflow-hidden border-t border-white/10 bg-[#0a0d13]"
    >
      <div className="technical-grid absolute inset-0 opacity-25" aria-hidden="true" />
      <div
        data-parallax-speed="0.05"
        data-parallax-local
        className="consultancy-atmosphere absolute inset-0"
        aria-hidden="true"
      />

      <div className="relative mx-auto max-w-[1536px] px-6 py-20 sm:px-10 sm:py-24 lg:px-20 lg:py-28">
        <div className="grid gap-14 lg:grid-cols-[minmax(0,600px)_1fr] lg:items-center lg:gap-16">
          <div>
            <div className="flex items-center gap-3">
              <span className="mono text-[10px] tracking-[0.3em] text-app-red">
                FOR CONSULTANCIES
              </span>
              <span className="h-px w-12 bg-app-red/50" />
            </div>

            <h2 className="mt-5 font-[family-name:var(--font-display)] text-[clamp(2.1rem,4.8vw,3.5rem)] font-extrabold leading-[1.02] tracking-[-0.03em] text-app-text">
              100 STUDENTS SHOULDN&apos;T MEAN{" "}
              <span className="bg-gradient-to-r from-[#5cc6ff] via-[#8f7bff] to-[#b46bff] bg-clip-text text-transparent">
                100 SPREADSHEETS.
              </span>
            </h2>

            <p className="mt-6 max-w-[520px] text-base leading-7 text-app-muted sm:text-lg">
              Give your team a clearer view of student job-search
              progress — without taking over each student&apos;s
              personal NERO workspace.
            </p>

            <div className="mt-8 flex items-start gap-3 rounded-xl border border-app-border-soft bg-app-panel/50 p-4">
              <Lock className="mt-0.5 h-4 w-4 shrink-0 text-app-blue" aria-hidden="true" />
              <p className="mono text-[11px] leading-6 tracking-[0.05em] text-app-body">
                VISIBILITY FOR THE CONSULTANCY.
                <br />
                OWNERSHIP FOR THE STUDENT.
              </p>
            </div>

            <div className="mt-10 flex flex-wrap gap-3">
              {sequence.map((step, index) => (
                <div key={step.title} className="flex items-center gap-3">
                  <span
                    data-reveal
                    data-reveal-delay={index * 100}
                    className="inline-flex items-center gap-2 rounded-full border border-app-border-soft bg-app-panel/70 px-4 py-2"
                  >
                    <step.icon className="h-3.5 w-3.5 text-app-blue" aria-hidden="true" />
                    <span className="mono text-[10px] tracking-[0.15em] text-app-text">
                      {step.title.toUpperCase()}
                    </span>
                  </span>
                  {index < sequence.length - 1 && (
                    <span className="h-px w-6 bg-app-border-strong" aria-hidden="true" />
                  )}
                </div>
              ))}
            </div>

            <div className="mt-10">
              <Link
                href="/register"
                className="app-focus-ring group inline-flex items-center justify-center gap-2 rounded-lg bg-crimson-fill px-6 py-3.5 text-sm font-medium text-white shadow-[0_0_28px_rgba(217,40,31,0.4)] transition hover:bg-crimson-fill-hover"
              >
                Explore NERO for Consultancies
                <span className="transition-transform group-hover:translate-x-1">
                  →
                </span>
              </Link>
            </div>
          </div>

          <div>
            <div
              data-parallax-speed="0.04"
              data-parallax-local
              className="grid grid-cols-6 gap-2.5 sm:grid-cols-8"
            >
              {STUDENT_DOTS.map((dot) => (
                <span
                  key={dot.id}
                  data-reveal
                  data-reveal-delay={dot.delay}
                  style={
                    {
                      "--reveal-distance": "8px",
                      "--reveal-rotate": `${dot.rotate}deg`,
                    } as CSSProperties
                  }
                  className={`flex aspect-square items-center justify-center rounded-lg border text-[9px] font-semibold ${STATE_CLASS[dot.state]}`}
                  aria-hidden="true"
                >
                  <Users className="h-3.5 w-3.5" aria-hidden="true" />
                </span>
              ))}
            </div>

            <p className="mono mt-5 text-center text-[9px] leading-5 tracking-[0.15em] text-app-faint">
              ILLUSTRATIVE — PROGRESS SIGNALS ONLY, NOT PERSONAL DATA
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
