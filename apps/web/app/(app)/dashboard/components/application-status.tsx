import { ListChecks } from "lucide-react";
import Panel from "@/components/app/panel";

type Props = {
  applications: {
    available: boolean;
  };
};

export default function ApplicationStatus({ applications }: Props) {
  return (
    <Panel>
      <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-app-faint">
        Application Status
      </div>

      <div className="mt-4 flex items-start gap-3 rounded-lg border border-app-border bg-app-bg p-4">
        <ListChecks
          className="mt-0.5 h-4 w-4 shrink-0 text-app-soft"
          aria-hidden="true"
        />

        <p className="text-sm leading-6 text-app-muted">
          {applications.available
            ? "Application tracking data is available."
            : "Application tracking isn't available yet. This module is on the AJI roadmap."}
        </p>
      </div>
    </Panel>
  );
}
