import Panel from "@/components/app/panel";
import Badge from "@/components/app/badge";
import type { DashboardData } from "@/lib/dashboard";

type Props = {
  resume: DashboardData["resume"];
  jobs: DashboardData["jobs"];
};

function formatEmploymentType(value: string): string {
  return value.replace(/_/g, " ");
}

export default function TodaysJobsPanel({ resume, jobs }: Props) {
  const resumeReady = resume.status === "ready";

  const subtitle = !resumeReady
    ? "Job discovery starts after your resume is ready."
    : jobs.today_count > 0
      ? `${jobs.today_count} new job${jobs.today_count === 1 ? "" : "s"} discovered today.`
      : "No new jobs discovered today.";

  const emptyTitle = !resumeReady
    ? "No jobs to display yet"
    : jobs.today_count > 0
      ? `${jobs.today_count} job${jobs.today_count === 1 ? "" : "s"} found today`
      : "No jobs to display yet";

  const emptyDescription = !resumeReady
    ? "Complete resume analysis to unlock job intelligence."
    : jobs.today_count > 0
      ? "Browse the full jobs list to see today's discoveries."
      : "NERO checks your tracked sources continuously.";

  return (
    <Panel as="div" padding="lg">
      <h2 className="text-xl font-bold tracking-tight text-app-text">
        Today&apos;s jobs
      </h2>

      <p className="mt-2 text-sm text-app-muted">{subtitle}</p>

      {jobs.today_employment_types.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-2">
          {jobs.today_employment_types.map((employmentType) => (
            <Badge key={employmentType} tone="blue" variant="soft">
              {formatEmploymentType(employmentType)}
            </Badge>
          ))}
        </div>
      )}

      <div className="mt-6 border-t border-app-border pt-6">
        <div className="text-sm font-bold text-app-body">{emptyTitle}</div>
        <p className="mt-2 text-xs text-app-soft">{emptyDescription}</p>
      </div>
    </Panel>
  );
}
