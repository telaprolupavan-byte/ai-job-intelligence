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
          How well a specific resume version demonstrates a specific job
          description&apos;s requirements — separate from Job Match. This is
          AJI&apos;s own estimate, not the employer&apos;s proprietary ATS
          score, and it is not a prediction of whether you&apos;ll be hired.
        </p>

        <div className="mt-6">
          <EmptyState
            icon={ClipboardList}
            title="Calculate ATS Alignment from a job listing"
            description="ATS Alignment is calculated per job against your resume. Open a job on the Jobs page and use its 'Calculate ATS Alignment' action to see matched, partial, and missing requirements with supporting evidence."
            action={<AppButton href="/jobs">Go to Jobs →</AppButton>}
          />
        </div>
      </Container>
    </div>
  );
}
