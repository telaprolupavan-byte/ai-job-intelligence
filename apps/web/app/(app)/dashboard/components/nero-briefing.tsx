import Panel from "@/components/app/panel";
import SectionLabel from "@/components/app/section-label";
import AppButton from "@/components/app/app-button";
import type { DashboardData } from "@/lib/dashboard";

type Props = {
  resume: DashboardData["resume"];
  validation: DashboardData["validation"];
  ats: DashboardData["ats"];
};

type Briefing = {
  title: string;
  body: string;
  ctaLabel: string;
  ctaHref: string;
  footnote: string;
};

function briefingFor({ resume, validation, ats }: Props): Briefing {
  if (resume.status !== "ready") {
    return {
      title: "Upload your resume",
      body: "NERO can't analyze what it hasn't seen yet — upload a resume to get started.",
      ctaLabel: "Upload Resume",
      ctaHref: "/resume",
      footnote: "NERO will explain what needs attention before you continue.",
    };
  }

  if (validation.status !== "analyzed") {
    return {
      title: "Your next step",
      body: "Before searching for jobs, make sure your resume has been analyzed and validated.",
      ctaLabel: "Analyze Resume",
      ctaHref: "/resume",
      footnote: "NERO will explain what needs attention before you continue.",
    };
  }

  if (ats.status === "not_checked") {
    return {
      title: "Check your ATS alignment",
      body: "Your resume is analyzed — see how it aligns with a specific job's requirements next.",
      ctaLabel: "Browse Jobs",
      ctaHref: "/jobs",
      footnote: "NERO will explain what needs attention before you continue.",
    };
  }

  return {
    title: "You're up to date",
    body: "Your resume is analyzed and ready. Keep exploring new opportunities as they appear.",
    ctaLabel: "View Jobs",
    ctaHref: "/jobs",
    footnote: "NERO will keep watching for what changes next.",
  };
}

export default function NeroBriefing(props: Props) {
  const briefing = briefingFor(props);

  return (
    <Panel padding="lg" className="flex flex-col">
      <SectionLabel tone="blue">NERO Briefing</SectionLabel>

      <h2 className="mt-4 text-[22px] font-bold text-app-text">
        {briefing.title}
      </h2>

      <p className="mt-3 max-w-xl text-[15px] leading-6 text-app-body">
        {briefing.body}
      </p>

      <div className="mt-5">
        <AppButton href={briefing.ctaHref}>{briefing.ctaLabel}</AppButton>
      </div>

      <p className="mt-5 text-xs text-app-muted">{briefing.footnote}</p>
    </Panel>
  );
}
