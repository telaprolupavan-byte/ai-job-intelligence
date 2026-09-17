import Link from "next/link";

const capabilities = [
  {
    number: "01",
    title: "DISCOVER",
    description:
      "Search across U.S. opportunities and surface jobs that actually fit your profile.",
  },
  {
    number: "02",
    title: "MATCH",
    description:
      "Measure your fit against the role using skills, experience, requirements, and preferences.",
  },
  {
    number: "03",
    title: "ATS",
    description:
      "Analyze how ready your resume is for the specific opportunity before you apply.",
  },
  {
    number: "04",
    title: "OPTIMIZE",
    description:
      "Improve your resume truthfully around the requirements that matter most.",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen overflow-hidden bg-app-bg">
      {/* Navigation */}
      <header className="relative z-50 border-b border-white/10">
        <nav className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6 lg:px-8">
          <Link href="/" className="group flex items-center gap-3">
            <div className="relative flex h-9 w-9 items-center justify-center">
              <div className="absolute inset-0 rounded-full border border-app-red/50" />
              <div className="absolute h-2 w-2 rounded-full bg-app-red red-text-glow" />
            </div>

            <div>
              <div className="text-sm font-semibold tracking-tight">
                AI JOB
              </div>
              <div className="mono text-[9px] tracking-[0.22em] text-app-muted">
                INTELLIGENCE
              </div>
            </div>
          </Link>

          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="hidden px-4 py-2 text-sm text-app-muted transition hover:text-app-text sm:block"
            >
              Sign in
            </Link>

            <Link
              href="/register"
              className="rounded-lg bg-crimson-fill px-5 py-2.5 text-sm font-medium text-white transition hover:bg-crimson-fill-hover"
            >
              Get started
            </Link>
          </div>
        </nav>
      </header>

      {/* Hero */}
      <section className="relative min-h-[calc(100vh-80px)]">
        <div className="technical-grid absolute inset-0 opacity-50" />
        <div className="red-atmosphere absolute inset-0" />
        <div className="web-atmosphere absolute inset-0 opacity-80" />

        {/* Decorative lines */}
        <div className="absolute left-[8%] top-1/3 hidden h-px w-32 bg-gradient-to-r from-transparent via-app-red/40 to-transparent lg:block" />
        <div className="absolute right-[8%] top-2/3 hidden h-px w-32 bg-gradient-to-r from-transparent via-app-red/40 to-transparent lg:block" />

        <div className="relative mx-auto flex min-h-[calc(100vh-80px)] max-w-7xl items-center px-6 py-24 lg:px-8">
          <div className="w-full">
            <div className="mb-8 flex items-center gap-3">
              <span className="mono text-[10px] tracking-[0.3em] text-app-red">
                01 / AI JOB INTELLIGENCE
              </span>

              <span className="h-px w-12 bg-app-red/50" />
            </div>

            <h1 className="max-w-5xl font-[family-name:var(--font-display)] text-[clamp(3.2rem,8vw,7.5rem)] font-bold leading-[0.9] tracking-[-0.03em]">
              FIND
              <br />
              BETTER
              <br />
              <span className="text-app-muted">OPPORTUNITIES.</span>
            </h1>

            <div className="mt-12 grid max-w-4xl gap-10 lg:grid-cols-[1fr_280px] lg:items-end">
              <div>
                <p className="max-w-2xl text-base leading-7 text-app-muted sm:text-lg">
                  Discover relevant jobs, understand your match, analyze ATS
                  readiness, and improve your resume before you apply.
                </p>

                <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                  <Link
                    href="/register"
                    className="group inline-flex items-center justify-center gap-3 rounded-lg bg-crimson-fill px-6 py-3.5 text-sm font-medium text-white transition hover:bg-crimson-fill-hover"
                  >
                    Start your search
                    <span className="transition-transform group-hover:translate-x-1">
                      →
                    </span>
                  </Link>

                  <Link
                    href="#system"
                    className="inline-flex items-center justify-center rounded-lg border border-white/10 bg-white/[0.02] px-6 py-3.5 text-sm font-medium transition hover:bg-white/[0.05]"
                  >
                    Explore the system
                  </Link>
                </div>
              </div>

              <div className="border-l border-white/10 pl-6">
                <div className="mono text-[10px] tracking-[0.2em] text-app-muted">
                  SYSTEM STATUS
                </div>

                <div className="mt-3 flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-app-red shadow-[0_0_12px_rgba(255,59,48,0.6)]" />
                  <span className="text-sm">INTELLIGENCE ONLINE</span>
                </div>

                <div className="mono mt-3 text-[10px] leading-5 text-app-muted">
                  DISCOVER / MATCH / ATS / OPTIMIZE
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="absolute bottom-8 left-1/2 -translate-x-1/2">
          <div className="mono text-[9px] tracking-[0.3em] text-app-muted">
            SCROLL TO EXPLORE
          </div>
        </div>
      </section>

      {/* System */}
      <section id="system" className="border-t border-white/10">
        <div className="mx-auto max-w-7xl px-6 py-24 lg:px-8 lg:py-32">
          <div className="grid gap-16 lg:grid-cols-[0.8fr_1.2fr]">
            <div>
              <div className="mono text-[10px] tracking-[0.3em] text-app-red">
                02 / THE SYSTEM
              </div>

              <h2 className="font-[family-name:var(--font-display)] mt-5 text-4xl font-semibold tracking-[-0.04em] sm:text-5xl">
                YOUR SEARCH.
                <br />
                <span className="text-app-muted">INTELLIGENTLY.</span>
              </h2>

              <p className="mt-6 max-w-md leading-7 text-app-muted">
                One workflow for discovering opportunities and understanding
                exactly where you stand before you apply.
              </p>
            </div>

            <div className="grid gap-px overflow-hidden border border-white/10 bg-white/10 sm:grid-cols-2">
              {capabilities.map((item) => (
                <div
                  key={item.number}
                  className="group bg-app-panel p-7 transition hover:bg-app-panel-strong"
                >
                  <div className="flex items-start justify-between">
                    <span className="mono text-[10px] text-app-red">
                      {item.number}
                    </span>

                    <span className="text-app-muted transition group-hover:translate-x-1 group-hover:text-app-red">
                      →
                    </span>
                  </div>

                  <h3 className="mt-12 text-lg font-semibold tracking-tight">
                    {item.title}
                  </h3>

                  <p className="mt-3 text-sm leading-6 text-app-muted">
                    {item.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Match intelligence */}
      <section className="relative border-t border-white/10">
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
      <section className="border-t border-white/10">
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
      <section className="border-t border-white/10">
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