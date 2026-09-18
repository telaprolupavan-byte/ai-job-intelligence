import Panel from "@/components/app/panel";
import SectionLabel from "@/components/app/section-label";
import Badge from "@/components/app/badge";

export default function ApplicationActivity() {
  return (
    <Panel as="div" padding="lg" className="flex h-full flex-col">
      <SectionLabel tone="faint">Application Activity</SectionLabel>

      <h2 className="mt-5 text-lg font-bold tracking-tight text-app-text">
        No applications yet
      </h2>

      <p className="mt-3 text-sm leading-6 text-app-body">
        Applications will appear here as you track them.
      </p>

      <div className="mt-auto pt-6">
        <Badge tone="neutral" variant="soft">
          0 Active
        </Badge>
      </div>
    </Panel>
  );
}
