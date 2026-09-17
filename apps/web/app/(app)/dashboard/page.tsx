"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { getCurrentUser } from "@/lib/auth";
import { getDashboard, DashboardData } from "@/lib/dashboard";
import { ApiError } from "@/lib/api";
import Container from "@/components/app/container";
import AppButton from "@/components/app/app-button";
import ErrorState from "@/components/app/error-state";
import { Skeleton } from "@/components/app/skeleton";

import IntelligenceCard from "./components/intelligence-card";
import QuickActions from "./components/quick-actions";
import Opportunities from "./components/opportunities";
import ApplicationStatus from "./components/application-status";

function timeBasedGreeting(): string {
  const hour = new Date().getHours();

  if (hour < 5) return "Good night";
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export default function DashboardPage() {
  const router = useRouter();

  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let mounted = true;

    async function loadDashboard() {
      setLoading(true);

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
        setLoadError(null);
      } catch (err) {
        if (!mounted) return;

        const isAuthFailure =
          (err instanceof Error && err.message === "Not authenticated") ||
          (err instanceof ApiError && [401, 403].includes(err.status));

        if (isAuthFailure) {
          router.replace("/login");
          return;
        }

        setLoadError(
          "We could not load your career intelligence data right now.",
        );
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
  }, [router, reloadKey]);

  if (loading) {
    return (
      <div className="bg-app-bg">
        <Container>
          <Skeleton className="h-40 w-full" />

          <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-32 w-full" />
            ))}
          </div>

          <div className="mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-14 w-full" />
            ))}
          </div>

          <div className="mt-10 grid gap-6 xl:grid-cols-[1.5fr_1fr]">
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        </Container>
      </div>
    );
  }

  if (loadError || !dashboard) {
    return (
      <div className="bg-app-bg">
        <Container>
          <ErrorState
            title="Dashboard unavailable"
            message={
              loadError ?? "We could not load your career intelligence data."
            }
            onRetry={() => setReloadKey((key) => key + 1)}
          />
        </Container>
      </div>
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

  const resumeDetail = dashboard.resume.name ?? "UPLOAD A RESUME TO BEGIN";
  const greeting = timeBasedGreeting();

  return (
    <div className="bg-app-bg text-app-text">
      <div className="relative overflow-hidden">
        {/* Technical atmosphere — decorative only, kept low-contrast */}
        <div className="pointer-events-none absolute inset-0 opacity-25" aria-hidden="true">
          <div className="absolute left-[10%] top-0 h-[380px] w-[380px] rounded-full bg-app-blue-soft/20 blur-[110px]" />
          <div className="absolute right-[-80px] top-[120px] h-[320px] w-[320px] rounded-full bg-app-red-soft/25 blur-[110px]" />

          <div
            className="absolute inset-0 opacity-[0.06]"
            style={{
              backgroundImage:
                "linear-gradient(var(--color-app-blue) 1px, transparent 1px), linear-gradient(90deg, var(--color-app-blue) 1px, transparent 1px)",
              backgroundSize: "70px 70px",
            }}
          />
        </div>

        <Container className="relative">
          {/* Hero — compact by design: one line of context, one primary action */}
          <section className="glass-panel relative overflow-hidden rounded-2xl border border-app-border">
            <div
              aria-hidden="true"
              className="absolute right-0 top-0 h-full w-[35%] bg-gradient-to-l from-app-blue-soft/15 to-transparent"
            />

            <div className="relative flex flex-col gap-5 px-6 py-6 sm:flex-row sm:items-center sm:justify-between md:px-8 md:py-7">
              <div className="min-w-0">
                <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-app-red">
                  Command Center
                </div>

                <h1 className="mt-2 font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight sm:text-3xl">
                  {greeting},{" "}
                  <span className="text-app-blue">
                    {dashboard.user.email.split("@")[0]}
                  </span>
                  .
                </h1>

                <p className="mt-2 max-w-xl text-sm leading-6 text-app-muted">
                  Your career intelligence is ready — resume analysis, job
                  matching, and discovery in one place.
                </p>
              </div>

              <AppButton href="/resume" className="shrink-0">
                Analyze Your Resume
                <span aria-hidden="true">→</span>
              </AppButton>
            </div>
          </section>

          {/* Intelligence */}
          <section className="mt-6">
            <div className="mb-3 font-mono text-[10px] uppercase tracking-[0.25em] text-app-faint">
              Intelligence Summary
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <IntelligenceCard
                label="Today's Jobs"
                value={dashboard.jobs.available ? "Available" : "—"}
                detail={
                  dashboard.jobs.available
                    ? "BROWSE OPEN POSITIONS"
                    : "MODULE NOT AVAILABLE"
                }
                accent="red"
                href={dashboard.jobs.available ? "/jobs" : undefined}
              />

              <IntelligenceCard
                label="ATS Readiness"
                value={atsValue}
                detail={atsDetail}
                accent="blue"
                href="/ats"
              />

              <IntelligenceCard
                label="Resume Status"
                value={resumeValue}
                detail={resumeDetail}
                accent="red"
                href="/resume"
              />

              <IntelligenceCard
                label="Applications"
                value={dashboard.applications.available ? "Available" : "—"}
                detail={
                  dashboard.applications.available
                    ? "TRACK YOUR PIPELINE"
                    : "MODULE NOT AVAILABLE"
                }
                accent="blue"
                href={
                  dashboard.applications.available
                    ? "/applications"
                    : undefined
                }
              />
            </div>
          </section>

          {/* Quick Actions */}
          <div className="mt-6">
            <QuickActions />
          </div>

          {/* Jobs + Applications */}
          <section className="mt-8 grid gap-6 xl:grid-cols-[1.5fr_1fr]">
            <Opportunities />

            <ApplicationStatus applications={dashboard.applications} />
          </section>

          {/* Footer */}
          <footer className="mt-10 flex flex-col gap-3 border-t border-app-border pt-6 pb-8 text-[10px] md:flex-row md:items-center md:justify-between">
            <div className="font-mono uppercase tracking-[0.2em] text-app-faint">
              AI JOB INTELLIGENCE / PERSONAL CAREER SYSTEM
            </div>

            <div className="font-mono uppercase tracking-wider text-app-blue">
              BUILDING THE NEXT OPPORTUNITY
            </div>
          </footer>
        </Container>
      </div>
    </div>
  );
}
