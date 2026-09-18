"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { getCurrentUser } from "@/lib/auth";
import { getDashboard, DashboardData } from "@/lib/dashboard";
import { ApiError } from "@/lib/api";
import Container from "@/components/app/container";
import ErrorState from "@/components/app/error-state";
import SectionLabel from "@/components/app/section-label";
import { Skeleton } from "@/components/app/skeleton";

import ResumeStatusBar from "./components/resume-status-bar";
import MetricCard from "./components/metric-card";
import NeroBriefing from "./components/nero-briefing";
import ApplicationActivity from "./components/application-activity";
import TodaysJobsPanel from "./components/todays-jobs-panel";

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
          <Skeleton className="h-24 w-full" />

          <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-32 w-full" />
            ))}
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-[2fr_1fr]">
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>

          <Skeleton className="mt-6 h-56 w-full" />
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
    dashboard.ats.score !== null ? `${Math.round(dashboard.ats.score)}%` : "—";

  return (
    <div className="bg-app-bg text-app-text">
      <Container>
        {/* Page header */}
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
          <div>
            <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight text-app-text">
              Dashboard
            </h1>

            <p className="mt-1 text-[15px] text-app-muted">
              Your job intelligence, in one place.
            </p>
          </div>

          <SectionLabel tone="faint" className="pt-2">
            Today
          </SectionLabel>
        </div>

        {/* Resume / ATS status strip */}
        <div className="mt-6">
          <ResumeStatusBar resume={dashboard.resume} ats={dashboard.ats} />
        </div>

        {/* Metric cards */}
        <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Today's Jobs"
            value={String(dashboard.jobs.today_count)}
            caption="New opportunities"
            accent="blue"
          />

          <MetricCard
            label="Applications"
            value="0"
            caption="Active applications"
            accent="red"
          />

          <MetricCard
            label="ATS Score"
            value={atsValue}
            caption="Resume readiness"
            accent="amber"
          />

          <MetricCard
            label="Resume Validation"
            value="Pending"
            caption="Complete your first analysis"
            accent="success"
          />
        </div>

        {/* Briefing + Application activity */}
        <div className="mt-6 grid gap-6 xl:grid-cols-[2fr_1fr]">
          <NeroBriefing resume={dashboard.resume} ats={dashboard.ats} />
          <ApplicationActivity />
        </div>

        {/* Today's jobs */}
        <div className="mt-6">
          <TodaysJobsPanel resume={dashboard.resume} jobs={dashboard.jobs} />
        </div>

        {/* Footer */}
        <footer className="mt-10 flex flex-col gap-2 border-t border-app-border pt-6 pb-8 text-[10px] font-bold uppercase tracking-[0.2em] text-app-soft sm:flex-row sm:items-center sm:justify-between">
          <div>NERO • AI Job Intelligence</div>
          <div className="font-medium normal-case tracking-normal">
            Dashboard / V1
          </div>
        </footer>
      </Container>
    </div>
  );
}
