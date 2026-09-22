"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import AppButton from "@/components/app/app-button";
import Container from "@/components/app/container";
import NeroCharacterState from "@/components/app/nero-character-state";
import NeroErrorCard from "@/components/app/nero-error-card";
import Panel from "@/components/app/panel";
import { cn } from "@/lib/utils";
import { submitJob } from "@/lib/jobs";

// AJI-022 — Submit Job. Figma: 133:72 (default), 133:164 (analyzing),
// 133:197 (error), 133:239 (mobile).
//
// The states map directly onto one synchronous request: default ->
// analyzing while POST /jobs/submissions is in flight -> ready (navigate
// to the job's understanding view on /jobs) or error. There is no
// background job or polling behind "analyzing".

type SubmitStatus = "idle" | "analyzing" | "error";

// Server-side limit (apps/api/schemas.py JOB_SUBMISSION_MAX_CONTENT_LENGTH).
const MAX_CONTENT_LENGTH = 50_000;

const HEADER_COPY: Record<SubmitStatus, { title: string; description: string }> =
  {
    idle: {
      title: "Add a job for NERO to understand",
      description:
        "Paste the job description below. NERO will extract the role, requirements, responsibilities, and other job intelligence without changing the original content.",
    },
    analyzing: {
      title: "NERO is analyzing the job",
      description:
        "We’re extracting requirements, responsibilities, qualifications, and other job signals from the submitted posting.",
    },
    error: {
      title: "We couldn’t understand this job",
      description:
        "The job content could not be processed safely. Review the text and try again.",
    },
  };

const BUTTON_LABEL: Record<SubmitStatus, string> = {
  idle: "Analyze job",
  analyzing: "Analyzing…",
  error: "Try again",
};

const LABEL_CLASS =
  "mb-0.5 block text-[13px] text-app-body md:text-sm md:font-medium";

const FIELD_CLASS =
  "w-full rounded-[12px] border border-app-border bg-app-panel-strong px-3.5 text-[13px] text-app-text outline-none transition-colors placeholder:text-app-muted focus:border-app-blue disabled:cursor-not-allowed md:rounded-[10px] md:bg-app-panel md:px-6 md:font-medium";

export default function SubmitJobPage() {
  const router = useRouter();

  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [content, setContent] = useState("");
  const [status, setStatus] = useState<SubmitStatus>("idle");

  const isAnalyzing = status === "analyzing";
  const header = HEADER_COPY[status];

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    if (isAnalyzing) return;

    setStatus("analyzing");

    try {
      const result = await submitJob({ content, title, company });
      router.push(`/jobs?job=${encodeURIComponent(result.job.id)}`);
    } catch (err) {
      console.error(err);
      setStatus("error");
    }
  }

  return (
    <div className="bg-app-bg text-app-text">
      <Container>
        {/* HEADER — desktop copy follows the request state; mobile has a
            single static header (133:239). */}
        <header>
          <div className="hidden whitespace-pre text-xs font-medium text-app-blue md:block">
            {"AJI-022  /  JOB SUBMISSION"}
          </div>

          <h1 className="text-[22px] font-bold text-app-text md:mt-4 md:text-[32px]">
            <span className="md:hidden">Submit a job</span>
            <span className="hidden md:inline">{header.title}</span>
          </h1>

          <p className="mt-2 text-xs text-app-muted md:mt-5 md:max-w-[1040px] md:text-[15px]">
            <span className="md:hidden">
              Paste a job posting and let NERO understand it.
            </span>
            <span className="hidden md:inline">{header.description}</span>
          </p>
        </header>

        <Panel
          padding="none"
          className="mt-6 max-w-[1080px] px-5 pb-8 pt-[22px] md:mt-[76px] md:rounded-[12px] md:px-8 md:pb-[52px] md:pt-7"
        >
          <form onSubmit={handleSubmit} aria-busy={isAnalyzing}>
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between md:gap-6">
              <div className="min-w-0">
                <h2 className="text-base font-bold text-app-text md:text-[22px] md:font-medium md:text-app-body">
                  Job details
                </h2>

                <p className="mt-4 text-[13px] text-app-body md:mt-2 md:text-sm md:font-medium">
                  <span className="md:hidden">
                    Paste the original job description below. NERO will
                    extract the important job signals without changing the
                    source.
                  </span>
                  <span className="hidden md:inline">
                    Paste the original job posting. Keep the wording intact
                    so NERO can trace its analysis back to the source.
                  </span>
                </p>
              </div>

              {status === "error" ? (
                <NeroErrorCard className="shrink-0 md:max-w-sm" />
              ) : (
                <NeroCharacterState
                  state={isAnalyzing ? "Analyzing" : "Idle"}
                  className="hidden w-[76px] shrink-0 md:flex"
                />
              )}
            </div>

            <div className="mt-4 grid gap-4 md:mt-3.5 md:grid-cols-[490fr_498fr] md:gap-7">
              <div>
                <label htmlFor="submit-job-title" className={LABEL_CLASS}>
                  Job title
                </label>
                <input
                  id="submit-job-title"
                  type="text"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="e.g. Senior Software Engineer"
                  maxLength={500}
                  disabled={isAnalyzing}
                  className={cn(FIELD_CLASS, "h-12")}
                />
              </div>

              <div>
                <label htmlFor="submit-job-company" className={LABEL_CLASS}>
                  Company
                </label>
                <input
                  id="submit-job-company"
                  type="text"
                  value={company}
                  onChange={(event) => setCompany(event.target.value)}
                  placeholder="e.g. Acme Inc."
                  maxLength={255}
                  disabled={isAnalyzing}
                  className={cn(FIELD_CLASS, "h-12")}
                />
              </div>
            </div>

            <div className="mt-4">
              <label htmlFor="submit-job-content" className={LABEL_CLASS}>
                Job description
              </label>

              {isAnalyzing ? (
                <div
                  id="submit-job-content"
                  aria-live="polite"
                  className={cn(
                    FIELD_CLASS,
                    "h-[190px] pt-[22px] opacity-55 md:h-[360px] md:pt-6",
                  )}
                >
                  NERO is analyzing the submitted job content…
                </div>
              ) : (
                <textarea
                  id="submit-job-content"
                  value={content}
                  onChange={(event) => setContent(event.target.value)}
                  placeholder="Paste the full job description here…"
                  required
                  maxLength={MAX_CONTENT_LENGTH}
                  className={cn(
                    FIELD_CLASS,
                    "block h-[190px] resize-none pt-[22px] md:h-[360px] md:pt-6",
                  )}
                />
              )}
            </div>

            <div className="mt-[30px] flex flex-col md:mt-5 md:flex-row md:items-start md:justify-between md:gap-6">
              <p className="hidden text-sm font-medium text-app-body md:block">
                Your submitted job is private to your NERO account.
              </p>

              <AppButton
                type="submit"
                disabled={isAnalyzing}
                className={cn(
                  "h-[42px] w-[180px] self-start rounded-[9px] px-4 text-xs normal-case tracking-normal disabled:cursor-wait disabled:opacity-100",
                  "md:mt-[18px] md:w-[170px] md:self-auto md:rounded-[10px] md:text-sm md:font-medium",
                  status === "idle" ? "text-app-text md:text-white" : "text-app-body",
                )}
              >
                {BUTTON_LABEL[status]}
              </AppButton>
            </div>
          </form>
        </Panel>
      </Container>
    </div>
  );
}
