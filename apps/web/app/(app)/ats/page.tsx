import { ClipboardList } from "lucide-react";
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
          icon={ClipboardList}
          title="ATS Alignment is coming soon"
          description="ATS Alignment will score how well a specific resume version aligns with a specific job description, separate from Job Match. It's on the AJI roadmap and will appear here once it ships."
          action={<AppButton href="/dashboard">← Back to Dashboard</AppButton>}
        />
      </Container>
    </main>
  );
}
