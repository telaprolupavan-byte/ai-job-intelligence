import Panel from "@/components/app/panel";
import SectionLabel from "@/components/app/section-label";
import Badge from "@/components/app/badge";
import type { DashboardData } from "@/lib/dashboard";

type Props = {
  applications: DashboardData["applications"];
};

export default function ApplicationActivity({ applications }: Props) {
  const hasActivity = applications.available && applications.active_count > 0;

  return (
    <Panel padding="lg" className="flex flex-col">
      <SectionLabel tone="muted">Application Activity</SectionLabel>

      <h2 className="mt-6 text-lg font-bold text-app-text">
        {hasActivity
          ? `${applications.active_count} active application${applications.active_count === 1 ? "" : "s"}`
          : "No applications yet"}
      </h2>

      <p className="mt-3 text-[13px] leading-6 text-app-body">
        {hasActivity
          ? "Keep tracking these opportunities as they move through your pipeline."
          : "Applications will appear here as you track them."}
      </p>

      <div className="mt-5">
        <Badge tone="neutral-soft">
          {applications.active_count} ACTIVE
        </Badge>
      </div>
    </Panel>
  );
}
