import { ListChecks } from "lucide-react";
import Container from "@/components/app/container";
import EmptyState from "@/components/app/empty-state";
import AppButton from "@/components/app/app-button";

export default function Page() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-app-bg px-6 text-app-text">
      <Container size="narrow" className="py-0">
        <div className="mb-6 text-center font-mono text-[10px] uppercase tracking-[0.25em] text-app-red">
          Intelligence Module
        </div>

        <EmptyState
          icon={ListChecks}
          title="Application tracking is coming soon"
          description="Tracking the jobs you've applied to, their status, and outcomes is part of the AJI roadmap and will be activated in a future release."
          action={<AppButton href="/dashboard">← Back to Dashboard</AppButton>}
        />
      </Container>
    </main>
  );
}
