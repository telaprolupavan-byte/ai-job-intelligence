"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { getDashboard, DashboardData } from "@/lib/dashboard";
import { ApiError } from "@/lib/api";
import Container from "@/components/app/container";
import PageHeader from "@/components/app/page-header";
import SectionLabel from "@/components/app/section-label";
import ErrorState from "@/components/app/error-state";
import { Skeleton } from "@/components/app/skeleton";

import ResumeStatus from "./components/resume-status";
import MetricCard from "./components/metric-card";
import NeroBriefing from "./components/nero-briefing";
import ApplicationActivity from "./components/application-activity";
import TodayJobs from "./components/today-jobs";

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
        const data = await getDashboard();

        if (!mounted) return;

        setDashboard(data);
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
          <Skeleton className="h-16 w-64" />
          <Skeleton className="mt-8 h-24 w-full" />

          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-36 w-full" />
            ))}
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-[2fr_1fr]">
            <Skeleton className="h-64 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>

          <Skeleton className="mt-6 h-64 w-full" />
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

  const { resume, validation, ats, jobs, applications, last_checked_at } =
    dashboard;

  const resumeReady = resume.status === "ready";
  const atsValue = ats.score !== null ? `${ats.score}` : "—";

  return (
    <div className="bg-app-bg text-app-text">
      <Container>
        <PageHeader
          title="Dashboard"
          description="Your job intelligence, in one place."
          action={<SectionLabel tone="faint">Today</SectionLabel>}
        />

        <ResumeStatus
          resume={resume}
          validation={validation}
          ats={ats}
          lastCheckedAt={last_checked_at}
        />

        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard
            label="Today's Jobs"
            value={jobs.today_count}
            meta="New opportunities"
            accent="blue"
            href="/jobs"
          />

          <MetricCard
            label="Applications"
            value={applications.active_count}
            meta="Active applications"
            accent="red"
            href={applications.available ? "/applications" : undefined}
          />

          <MetricCard
            label="ATS Score"
            value={atsValue}
            meta="Resume readiness"
            accent="amber"
            href="/ats"
          />

          <MetricCard
            label="Resume Validation"
            value={validation.status === "analyzed" ? "Analyzed" : "Pending"}
            meta={
              validation.status === "analyzed"
                ? "Latest analysis on file"
                : "Complete your first analysis"
            }
            accent="success"
            href="/resume"
          />
        </div>

        <div className="mt-6 grid gap-6 xl:grid-cols-[2fr_1fr]">
          <NeroBriefing resume={resume} validation={validation} ats={ats} />
          <ApplicationActivity applications={applications} />
        </div>

        <div className="mt-6">
          <TodayJobs jobs={jobs} resumeReady={resumeReady} />
        </div>

        <footer className="mt-10 flex flex-col gap-3 border-t border-app-border pt-6 pb-8 text-[10px] md:flex-row md:items-center md:justify-between">
          <div className="font-mono uppercase tracking-[0.2em] text-app-faint">
            NERO • AI JOB INTELLIGENCE
          </div>

          <div className="font-mono uppercase tracking-wider text-app-faint">
            Dashboard / V1
          </div>
        </footer>
      </Container>
    </div>
  );
}
