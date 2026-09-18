"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import {
  APPLICATION_STATUSES,
  getApplicationDetail,
  updateApplicationStatus,
  type ApplicationDetail,
  type ApplicationStatus,
} from "@/lib/applications";
import { ApiError } from "@/lib/api";
import Container from "@/components/app/container";
import PageHeader from "@/components/app/page-header";
import Panel, { PanelHeader } from "@/components/app/panel";
import Badge from "@/components/app/badge";
import AppButton from "@/components/app/app-button";
import ErrorState from "@/components/app/error-state";
import { Skeleton } from "@/components/app/skeleton";

const STATUS_TONE: Record<
  ApplicationStatus,
  "neutral-soft" | "blue-soft" | "amber" | "success-soft" | "danger"
> = {
  saved: "neutral-soft",
  applied: "blue-soft",
  interviewing: "amber",
  offer: "success-soft",
  rejected: "danger",
  withdrawn: "neutral-soft",
};

function formatStatus(status: string): string {
  return status
    .split("_")
    .map((word) => word[0]?.toUpperCase() + word.slice(1))
    .join(" ");
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function ApplicationDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const applicationId = params.id;

  const [application, setApplication] = useState<ApplicationDetail | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [pendingStatus, setPendingStatus] = useState<ApplicationStatus | "">(
    "",
  );
  const [updating, setUpdating] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function load() {
      setLoading(true);

      try {
        const data = await getApplicationDetail(applicationId);
        if (!mounted) return;
        setApplication(data);
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

        if (err instanceof ApiError && err.status === 404) {
          setLoadError("This application could not be found.");
        } else {
          setLoadError("We could not load this application right now.");
        }
      } finally {
        if (mounted) setLoading(false);
      }
    }

    load();

    return () => {
      mounted = false;
    };
  }, [applicationId, router, reloadKey]);

  async function handleUpdateStatus() {
    if (!pendingStatus || !application) return;

    setUpdating(true);
    setUpdateError(null);

    try {
      await updateApplicationStatus(application.id, pendingStatus);
      setPendingStatus("");
      setReloadKey((key) => key + 1);
    } catch {
      setUpdateError("Could not update status. Please try again.");
    } finally {
      setUpdating(false);
    }
  }

  return (
    <div className="bg-app-bg text-app-text">
      <Container size="narrow">
        <Link
          href="/applications"
          className="inline-flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-app-muted hover:text-app-text"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          Back to Applications
        </Link>

        {loading ? (
          <div className="mt-6 space-y-4">
            <Skeleton className="h-10 w-64" />
            <Skeleton className="h-40 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : loadError || !application ? (
          <div className="mt-6">
            <ErrorState
              title="Application unavailable"
              message={loadError ?? "This application could not be loaded."}
              onRetry={() => setReloadKey((key) => key + 1)}
            />
          </div>
        ) : (
          <>
            <PageHeader
              title={application.job.title}
              description={
                application.job.company
                  ? `${application.job.company}${
                      application.job.location
                        ? ` · ${application.job.location}`
                        : ""
                    }`
                  : undefined
              }
              action={
                <div className="flex flex-col items-end gap-1">
                  <Badge tone={STATUS_TONE[application.status]}>
                    {formatStatus(application.status)}
                  </Badge>
                  {application.applied_at && (
                    <span className="font-mono text-[10px] uppercase tracking-wider text-app-faint">
                      Applied {formatDate(application.applied_at)}
                    </span>
                  )}
                </div>
              }
            />

            <div className="grid gap-6 lg:grid-cols-2">
              <Panel padding="none">
                <PanelHeader
                  eyebrow="Update Status"
                  description="NERO never applies on your behalf — record the status yourself after you've taken the action elsewhere."
                />

                <div className="flex flex-col gap-4 p-5">
                  <select
                    value={pendingStatus}
                    onChange={(event) =>
                      setPendingStatus(
                        event.target.value as ApplicationStatus | "",
                      )
                    }
                    className="h-11 rounded-lg border border-app-border bg-app-bg px-3 text-sm text-app-text"
                  >
                    <option value="">Select a new status…</option>
                    {APPLICATION_STATUSES.filter(
                      (status) => status !== application.status,
                    ).map((status) => (
                      <option key={status} value={status}>
                        {formatStatus(status)}
                      </option>
                    ))}
                  </select>

                  <AppButton
                    variant="secondary"
                    loading={updating}
                    disabled={!pendingStatus}
                    onClick={handleUpdateStatus}
                  >
                    Update Status
                  </AppButton>

                  {updateError && (
                    <p className="text-xs text-app-danger-text">
                      {updateError}
                    </p>
                  )}

                  {application.job.application_url && (
                    <AppButton
                      href={application.job.application_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      View Original Posting
                    </AppButton>
                  )}
                </div>
              </Panel>

              <Panel padding="none">
                <PanelHeader eyebrow="Timeline" title="Status History" />

                <div className="divide-y divide-app-border">
                  {application.status_history.map((event, index) => (
                    <div
                      key={`${event.status}-${event.created_at}-${index}`}
                      className="flex items-center justify-between gap-4 px-5 py-4"
                    >
                      <Badge tone={STATUS_TONE[event.status]}>
                        {formatStatus(event.status)}
                      </Badge>

                      <span className="font-mono text-[10px] uppercase tracking-wider text-app-faint">
                        {formatDate(event.created_at)}
                      </span>
                    </div>
                  ))}
                </div>
              </Panel>
            </div>
          </>
        )}
      </Container>
    </div>
  );
}
