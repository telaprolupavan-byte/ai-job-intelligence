"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ListChecks } from "lucide-react";

import { getApplications, type Application } from "@/lib/applications";
import { ApiError } from "@/lib/api";
import Container from "@/components/app/container";
import PageHeader from "@/components/app/page-header";
import Panel from "@/components/app/panel";
import Badge from "@/components/app/badge";
import EmptyState from "@/components/app/empty-state";
import ErrorState from "@/components/app/error-state";
import { Skeleton } from "@/components/app/skeleton";

const STATUS_TONE: Record<
  Application["status"],
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
  return new Date(value).toLocaleDateString(undefined, {
    dateStyle: "medium",
  });
}

export default function ApplicationsPage() {
  const router = useRouter();

  const [applications, setApplications] = useState<Application[] | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let mounted = true;

    async function load() {
      setLoading(true);

      try {
        const data = await getApplications();
        if (!mounted) return;
        setApplications(data);
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

        setLoadError("We could not load your applications right now.");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    load();

    return () => {
      mounted = false;
    };
  }, [router, reloadKey]);

  return (
    <div className="bg-app-bg text-app-text">
      <Container size="narrow">
        <PageHeader
          title="Applications"
          description="Track the jobs you've saved and applied to, and their status."
        />

        <div className="mt-6">
          {loading ? (
            <div className="space-y-3">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          ) : loadError ? (
            <ErrorState
              title="Applications unavailable"
              message={loadError}
              onRetry={() => setReloadKey((key) => key + 1)}
            />
          ) : !applications || applications.length === 0 ? (
            <EmptyState
              icon={ListChecks}
              title="No applications yet"
              description="Save a job from the Jobs page to start tracking it here."
            />
          ) : (
            <div className="space-y-3">
              {applications.map((application) => (
                <Link
                  key={application.id}
                  href={`/applications/${application.id}`}
                  className="block"
                >
                  <Panel padding="lg" interactive>
                    <div className="flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <div className="truncate text-base font-semibold text-app-text">
                          {application.job.title}
                        </div>
                        <div className="mt-1 truncate text-sm text-app-muted">
                          {application.job.company ?? "Unknown company"}
                          {application.job.location
                            ? ` · ${application.job.location}`
                            : ""}
                        </div>
                        {application.applied_at && (
                          <div className="mt-1 text-xs text-app-faint">
                            Applied {formatDate(application.applied_at)}
                          </div>
                        )}
                      </div>

                      <Badge
                        tone={STATUS_TONE[application.status]}
                        className="shrink-0"
                      >
                        {formatStatus(application.status)}
                      </Badge>
                    </div>
                  </Panel>
                </Link>
              ))}
            </div>
          )}
        </div>
      </Container>
    </div>
  );
}
