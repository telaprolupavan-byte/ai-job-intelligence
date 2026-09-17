import { Search } from "lucide-react";
import Panel, { PanelHeader } from "@/components/app/panel";
import EmptyState from "@/components/app/empty-state";
import AppButton from "@/components/app/app-button";

export default function Opportunities() {
  return (
    <Panel padding="none" strong>
      <PanelHeader
        eyebrow="Today's Opportunities"
        title="Jobs waiting for intelligence"
      />

      <div className="p-5">
        <EmptyState
          icon={Search}
          title="No opportunities yet"
          description="Job discovery isn't connected to your dashboard yet. Browse the full jobs list to search and filter live listings."
          action={<AppButton href="/jobs">Browse Jobs</AppButton>}
        />
      </div>
    </Panel>
  );
}
