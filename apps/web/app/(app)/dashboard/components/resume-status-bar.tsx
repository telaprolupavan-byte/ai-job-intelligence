import Panel from "@/components/app/panel";
import Badge from "@/components/app/badge";
import AppButton from "@/components/app/app-button";
import type { DashboardData } from "@/lib/dashboard";

type Props = {
  resume: DashboardData["resume"];
  ats: DashboardData["ats"];
};

export default function ResumeStatusBar({ resume, ats }: Props) {
  const atsValue = ats.score !== null ? `${Math.round(ats.score)}%` : "—";

  const lastChecked = ats.checked_at
    ? new Date(ats.checked_at).toLocaleDateString()
    : "Not yet analyzed";

  return (
    <Panel as="div" padding="lg">
      <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-1 flex-wrap items-center gap-x-10 gap-y-4">
          <div>
            <div className="text-sm font-bold text-app-body">
              Resume readiness
            </div>

            <Badge
              tone={resume.status === "ready" ? "blue" : "neutral"}
              variant="soft"
              className="mt-2"
            >
              {resume.status === "ready" ? "Ready for review" : "No resume yet"}
            </Badge>
          </div>

          <div>
            <div className="font-mono text-xs text-app-muted">ATS score</div>
            <div className="mt-2 text-2xl font-bold text-app-text">
              {atsValue}
            </div>
          </div>

          <div>
            <div className="font-mono text-xs text-app-muted">Validation</div>
            <Badge tone="red" variant="soft" className="mt-2">
              Pending
            </Badge>
          </div>

          <div>
            <div className="font-mono text-xs text-app-muted">
              Last checked
            </div>
            <div className="mt-2 text-sm font-medium text-app-body">
              {lastChecked}
            </div>
          </div>
        </div>

        <AppButton href="/resume" size="sm" className="shrink-0">
          Analyze Resume
        </AppButton>
      </div>
    </Panel>
  );
}
