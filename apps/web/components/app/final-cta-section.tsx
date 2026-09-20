import Link from "next/link";

/**
 * "Your next move starts with clarity." — the true close of the page,
 * after the existing "Same You. A Brighter Tomorrow." finale and the
 * Student/Consultancy split. Deliberately plain by comparison: no
 * ridge/skyline visual, no data streams, just a centered close with a
 * single slow-moving background wash — the spec asks for this section
 * to read as clean and subtle, not another cinematic beat.
 */
export default function FinalCtaSection() {
  return (
    <section
      id="final-cta"
      className="relative overflow-hidden border-t border-white/10 bg-[#090c11]"
    >
      <div
        data-parallax-speed="0.03"
        data-parallax-local
        className="final-cta-atmosphere absolute inset-0"
        aria-hidden="true"
      />

      <div className="relative mx-auto max-w-2xl px-6 py-24 text-center sm:px-10 sm:py-28 lg:py-32">
        <h2
          data-reveal
          className="font-[family-name:var(--font-display)] text-[clamp(2.25rem,5vw,3.5rem)] font-bold leading-[1.05] tracking-[-0.03em] text-app-text"
        >
          Your next move starts with{" "}
          <span className="bg-gradient-to-r from-[#5cc6ff] to-app-blue bg-clip-text text-transparent">
            clarity.
          </span>
        </h2>

        <p
          data-reveal
          data-reveal-delay="80"
          className="mx-auto mt-6 max-w-lg text-base leading-7 text-app-muted sm:text-lg"
        >
          Understand your resume. Find relevant opportunities. Know your
          match. Make your next move.
        </p>

        <div
          data-reveal
          data-reveal-delay="160"
          className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row"
        >
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
            href="#consultancy"
            className="app-focus-ring inline-flex items-center justify-center rounded-lg border border-app-border-soft bg-white/[0.02] px-7 py-3.5 text-sm font-medium text-app-text transition hover:bg-white/[0.05]"
          >
            For Consultancies
          </Link>
        </div>
      </div>
    </section>
  );
}
