"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { getCurrentUser } from "@/lib/auth";
import { getDashboard, DashboardData } from "@/lib/dashboard";

import IntelligenceCard from "./components/intelligence-card";
import QuickActions from "./components/quick-actions";
import Opportunities from "./components/opportunities";
import ApplicationStatus from "./components/application-status";

export default function DashboardPage() {
  const router = useRouter();

  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    async function loadDashboard() {
      try {
        const user = await getCurrentUser();

        if (!mounted) return;

        const data = await getDashboard();

        if (!mounted) return;

        setDashboard({
          ...data,
          user: {
            email: user.email,
          },
        });
      } catch {
        if (mounted) {
          router.replace("/login");
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadDashboard();

    return () => {
      mounted = false;
    };
  }, [router]);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#05070A]">
        <div className="font-mono text-xs uppercase tracking-[0.3em] text-[#1677E8]">
          Initializing Intelligence System...
        </div>
      </main>
    );
  }

  if (!dashboard) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#05070A] px-6">
        <div className="border border-[#8B0B18] bg-[#0B1626] p-8 text-center">
          <div className="font-mono text-xs uppercase tracking-wider text-[#E50920]">
            Dashboard unavailable
          </div>

          <p className="mt-3 text-sm text-[#8D9AAA]">
            We could not load your career intelligence data.
          </p>

          <Link
            href="/login"
            className="mt-6 inline-block bg-[#E50920] px-5 py-3 text-xs font-semibold uppercase tracking-wider text-white"
          >
            Return to Login
          </Link>
        </div>
      </main>
    );
  }

  const atsValue =
    dashboard.ats.score !== null ? `${dashboard.ats.score}%` : "—";

  const atsDetail =
    dashboard.ats.status === "pass"
      ? "READY · 80% TARGET"
      : dashboard.ats.status === "needs_improvement"
        ? "NEEDS IMPROVEMENT"
        : dashboard.ats.status === "not_checked"
          ? "NOT CHECKED"
          : "MODULE NOT AVAILABLE";

  const resumeValue =
    dashboard.resume.status === "ready" ? "READY" : "NOT READY";

  const resumeDetail =
    dashboard.resume.name ?? "UPLOAD A RESUME TO BEGIN";

  return (
    <main className="min-h-screen bg-[#05070A] text-[#F2F5F8]">
      <div className="relative overflow-hidden">
            {/* Technical atmosphere */}
            <div className="pointer-events-none absolute inset-0 opacity-40">
              <div className="absolute left-[15%] top-0 h-[500px] w-[500px] rounded-full bg-[#0B4EA2]/10 blur-[120px]" />
              <div className="absolute right-[-100px] top-[200px] h-[450px] w-[450px] rounded-full bg-[#E50920]/10 blur-[120px]" />

              <div
                className="absolute inset-0 opacity-[0.08]"
                style={{
                  backgroundImage:
                    "linear-gradient(#1677E8 1px, transparent 1px), linear-gradient(90deg, #1677E8 1px, transparent 1px)",
                  backgroundSize: "70px 70px",
                }}
              />
            </div>

            <div className="relative mx-auto max-w-[1600px] px-5 py-8 md:px-8 lg:px-10 lg:py-12">
              {/* Hero */}
              <section className="relative overflow-hidden border border-[#1A3048] bg-[#07111F]">
                <div className="absolute right-0 top-0 h-full w-[45%] bg-gradient-to-l from-[#0B4EA2]/10 to-transparent" />

                <div className="relative px-6 py-10 md:px-10 md:py-14">
                  <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#E50920]">
                    01 / COMMAND CENTER
                  </div>

                  <div className="mt-6 max-w-4xl">
                    <div className="font-mono text-xs uppercase tracking-[0.2em] text-[#5E7187]">
                      Hello, {dashboard.user.email.split("@")[0]}
                    </div>

                    <h1 className="mt-3 text-5xl font-bold tracking-[-0.04em] md:text-7xl lg:text-8xl">
                      GOOD
                      <br />
                      <span className="text-[#E50920]">MORNING.</span>
                    </h1>

                    <p className="mt-6 max-w-xl text-sm leading-7 text-[#8D9AAA] md:text-base">
                      Your career intelligence system is ready. Start with
                      resume intelligence while job discovery, ATS analysis,
                      and application tracking are being built.
                    </p>

                    <Link
                      href="/resume"
                      className="mt-8 inline-flex items-center gap-4 bg-[#E50920] px-6 py-4 text-xs font-bold uppercase tracking-[0.15em] text-white transition hover:bg-[#FF1E32]"
                    >
                      Analyze Your Resume
                      <span>→</span>
                    </Link>
                  </div>
                </div>

                <div className="absolute bottom-4 right-5 hidden font-mono text-[9px] uppercase tracking-[0.25em] text-[#1677E8] md:block">
                  SYSTEM / ONLINE
                </div>
              </section>

              {/* Intelligence */}
              <section className="mt-8">
                <div className="mb-4 font-mono text-[10px] uppercase tracking-[0.25em] text-[#5E7187]">
                  02 / INTELLIGENCE
                </div>

                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <IntelligenceCard
                    label="Today's Jobs"
                    value="—"
                    detail="MODULE NOT AVAILABLE"
                    accent="red"
                  />

                  <IntelligenceCard
                    label="ATS Readiness"
                    value={atsValue}
                    detail={atsDetail}
                    accent="blue"
                  />

                  <IntelligenceCard
                    label="Resume Status"
                    value={resumeValue}
                    detail={resumeDetail}
                    accent="red"
                  />

                  <IntelligenceCard
                    label="Applications"
                    value="—"
                    detail="MODULE NOT AVAILABLE"
                    accent="blue"
                  />
                </div>
              </section>

              {/* Quick Actions */}
              <div className="mt-8">
                <QuickActions />
              </div>

              {/* Jobs + Applications */}
              <section className="mt-10 grid gap-6 xl:grid-cols-[1.5fr_1fr]">
                <Opportunities />

                <ApplicationStatus
                  applications={dashboard.applications}
                />
              </section>

              {/* Footer */}
              <footer className="mt-12 flex flex-col gap-3 border-t border-[#1A3048] pt-6 text-[10px] md:flex-row md:items-center md:justify-between">
                <div className="font-mono uppercase tracking-[0.2em] text-[#5E7187]">
                  AI JOB INTELLIGENCE / PERSONAL CAREER SYSTEM
                </div>

                <div className="font-mono uppercase tracking-wider text-[#1677E8]">
                  BUILDING THE NEXT OPPORTUNITY
                </div>
              </footer>
            </div>
      </div>
    </main>
  );
}