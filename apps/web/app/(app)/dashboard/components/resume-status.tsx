import Panel from "@/components/app/panel";
import Badge from "@/components/app/badge";
import AppButton from "@/components/app/app-button";
import type { DashboardData } from "@/lib/dashboard";

type Props = {
  resume: DashboardData["resume"];
  validation: DashboardData["validation"];
  ats: DashboardData["ats"];
  lastCheckedAt: string | null;
};

function formatCheckedAt(lastCheckedAt: string | null): string {
  if (!lastCheckedAt) return "Not yet analyzed";

  return new Date(lastCheckedAt).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function ResumeStatus({
  resume,
  validation,
  ats,
  lastCheckedAt,
}: Props) {
  const atsValue = ats.score !== null ? `${ats.score}%` : "—";

  return (
    <Panel strong className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex flex-1 flex-wrap items-center gap-x-10 gap-y-4">
        <div>
          <div className="text-sm font-bold text-app-body">
            Resume readiness
          </div>

          <Badge
            tone={resume.status === "ready" ? "blue-soft" : "neutral-soft"}
            className="mt-2"
          >
            {resume.status === "ready" ? "Ready for review" : "Not ready"}
          </Badge>
        </div>

        <div>
          <div className="text-xs text-app-muted">ATS score</div>
          <div className="mt-1.5 text-2xl font-bold text-app-text">
            {atsValue}
          </div>
        </div>

        <div>
          <div className="text-xs text-app-muted">Validation</div>

          <Badge
            tone={validation.status === "analyzed" ? "success-soft" : "red-soft"}
            className="mt-2"
          >
            {validation.status === "analyzed" ? "Analyzed" : "Pending"}
          </Badge>
        </div>

        <div>
          <div className="text-xs text-app-muted">Last checked</div>
          <div className="mt-1.5 text-sm text-app-body">
            {formatCheckedAt(lastCheckedAt)}
          </div>
        </div>
      </div>

      <AppButton href="/resume" className="shrink-0">
        Analyze Resume
      </AppButton>
    </Panel>
  );
}
