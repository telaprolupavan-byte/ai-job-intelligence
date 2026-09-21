import type { CSSProperties } from "react";
import Link from "next/link";
import { AlertTriangle, Eye, Lock, Users, type LucideIcon } from "lucide-react";
import SectionHeading from "@/components/app/section-heading";

// Deterministic per-dot offsets (not random per render) so each dot's
// "settle" reveal is stable across renders — the illusion of many
// individuals coming into a structured view depends on each dot
// resolving to exactly the same tidy grid position every time.
//
// The state mix is deliberately weighted toward neutral. At one in
// five the amber "needs attention" tiles read as a scattering of
// warnings rather than an occasional flag, which both misrepresents
// the idea and turns an otherwise calm grid into visual noise.
const STUDENT_DOTS = Array.from({ length: 24 }, (_, i) => {
  const rotate = ((i * 37) % 13) - 6;
  const delay = (i % 8) * 55;
  const state = i % 11 === 3 ? "attention" : i % 4 === 1 ? "progress" : "neutral";
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
 *
 * RESTRAINED motion tier, matching the Student section it pairs with.
 */
export default function ConsultancySection() {
  return (
    <section
      id="consultancy"
      className="relative overflow-hidden border-t border-white/10 bg-[#0a0d13]"
    >
      <div className="technical-grid absolute inset-0 opacity-25" aria-hidden="true" />
      <div
        data-parallax-speed="0.07"
        data-parallax-local
        className="consultancy-atmosphere absolute inset-0"
        aria-hidden="true"
      />

      <div className="landing-shell landing-band">
        <div className="grid grid-cols-1 gap-12 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)] lg:items-center lg:gap-16">
          <div>
            <SectionHeading
              eyebrow="FOR CONSULTANCIES"
              title={
                <>
                  100 STUDENTS SHOULDN&apos;T MEAN{" "}
                  <span className="bg-gradient-to-r from-[#5cc6ff] via-[#8f7bff] to-[#b46bff] bg-clip-text text-transparent">
                    100 SPREADSHEETS.
                  </span>
                </>
              }
              lede="Give your team a clearer view of student job-search progress — without taking over each student's personal NERO workspace."
            />

            <div className="stack-md flex max-w-[520px] items-start gap-3 rounded-xl border border-app-border-soft bg-app-panel/50 p-4">
              <Lock className="mt-0.5 h-4 w-4 shrink-0 text-app-blue" aria-hidden="true" />
              <p className="mono text-[11px] leading-6 tracking-[0.05em] text-app-body">
                VISIBILITY FOR THE CONSULTANCY.
                <br />
                OWNERSHIP FOR THE STUDENT.
              </p>
            </div>

            <div className="stack-md flex flex-wrap items-center gap-x-3 gap-y-3">
              {sequence.map((step, index) => (
                // The connector renders BEFORE its chip, never after:
                // a trailing separator used to be left dangling at the
                // end of a wrapped line, which read as a rendering bug.
                <span key={step.title} className="inline-flex items-center gap-3">
                  {index > 0 && (
                    <span
                      className="h-px w-6 bg-app-border-strong"
                      aria-hidden="true"
                    />
                  )}
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
                </span>
              ))}
            </div>

            <div className="stack-md">
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

          <div className="mx-auto w-full max-w-[520px]">
            <div
              data-parallax-speed="0.05"
              data-parallax-scale-to="1.02"
              data-parallax-local
              className="grid grid-cols-6 gap-3 sm:grid-cols-8"
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
