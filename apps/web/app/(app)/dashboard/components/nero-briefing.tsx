import Panel from "@/components/app/panel";
import SectionLabel from "@/components/app/section-label";
import AppButton from "@/components/app/app-button";
import type { DashboardData } from "@/lib/dashboard";

type Props = {
  resume: DashboardData["resume"];
  ats: DashboardData["ats"];
};

// Deterministic, rule-based copy driven only by real dashboard state — never
// AI-generated. Each branch is a fixed template selected by a simple
// condition, not a model call.
function getBriefing(resume: Props["resume"], ats: Props["ats"]) {
  if (resume.status !== "ready") {
    return {
      title: "Your next step",
      body: "Upload your resume so NERO can start building your career intelligence.",
      action: "Upload Resume",
    };
  }

  if (ats.score === null) {
    return {
      title: "Your next step",
      body: "Before searching for jobs, make sure your resume has been analyzed and validated.",
      action: "Analyze Resume",
    };
  }

  return {
    title: "You're set up",
    body: "Your resume has been analyzed. Keep checking new jobs to run fresh alignment checks.",
    action: "View Jobs",
  };
}

export default function NeroBriefing({ resume, ats }: Props) {
  const briefing = getBriefing(resume, ats);
  const actionHref = briefing.action === "View Jobs" ? "/jobs" : "/resume";

  return (
    <Panel as="div" padding="lg" className="flex h-full flex-col">
      <SectionLabel tone="blue">NERO Briefing</SectionLabel>

      <h2 className="mt-5 text-[22px] font-bold tracking-tight text-app-text">
        {briefing.title}
      </h2>

      <p className="mt-3 max-w-xl text-[15px] leading-6 text-app-body">
        {briefing.body}
      </p>

      <div className="mt-6">
        <AppButton href={actionHref}>{briefing.action}</AppButton>
      </div>

      <p className="mt-auto pt-6 text-xs text-app-muted">
        NERO will explain what needs attention before you continue.
      </p>
    </Panel>
  );
}
