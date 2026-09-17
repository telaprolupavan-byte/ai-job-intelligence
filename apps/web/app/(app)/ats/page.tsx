import { ClipboardList } from "lucide-react";
import Container from "@/components/app/container";
import EmptyState from "@/components/app/empty-state";
import AppButton from "@/components/app/app-button";

export default function Page() {
  return (
    <div className="bg-app-bg text-app-text">
      <Container size="narrow">
        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-app-red">
          Intelligence Module
        </div>

        <h1 className="mt-3 font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight sm:text-3xl">
          ATS Alignment
        </h1>

        <p className="mt-2 max-w-2xl text-sm leading-6 text-app-muted">
          How well a specific resume version aligns with a specific job
          description — separate from Job Match.
        </p>

        <div className="mt-6">
          <EmptyState
            icon={ClipboardList}
            title="ATS Alignment is coming soon"
            description="This module is on the AJI roadmap and will appear here once it ships. Until then, every job shows 'Not calculated' rather than an estimated score."
            action={<AppButton href="/dashboard">← Back to Dashboard</AppButton>}
          />
        </div>
      </Container>
    </div>
  );
}
