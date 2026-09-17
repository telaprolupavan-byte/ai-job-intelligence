import { ListChecks } from "lucide-react";
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
          Applications
        </h1>

        <p className="mt-2 max-w-2xl text-sm leading-6 text-app-muted">
          Track the jobs you&apos;ve applied to, their status, and outcomes.
        </p>

        <div className="mt-6">
          <EmptyState
            icon={ListChecks}
            title="Application tracking is coming soon"
            description="This module is part of the AJI roadmap and will be activated in a future release."
            action={<AppButton href="/dashboard">← Back to Dashboard</AppButton>}
          />
        </div>
      </Container>
    </div>
  );
}
