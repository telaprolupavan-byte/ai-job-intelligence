// AJI-023 (Job Search) — everything the source told NERO about one opened
// job, in full. The opened JobCard renders this in place of the listing's
// 3-line description; the card itself keeps the title, badges and links,
// so none of those are repeated here.
//
// Unknown stays unknown. A key fact the source did not state is shown as
// "Not stated", never guessed or defaulted (no assumed currency, no
// inferred work arrangement); long-form sections the source did not
// provide are left out.

import type { Job } from "@/lib/jobs";
import {
  formatEmploymentType,
  formatPostedDate,
  formatSalary,
  formatValue,
} from "@/lib/job-format";

const NOT_STATED = "Not stated";

export default function JobDetails({ job }: { job: Job }) {
  const facts: { label: string; value: string | null }[] = [
    { label: "Company", value: job.company },
    { label: "Location", value: job.location },
    {
      label: "Work arrangement",
      value: job.remote_type ? formatValue(job.remote_type) : null,
    },
    {
      label: "Employment type",
      value: job.employment_type ? formatEmploymentType(job) : null,
    },
    { label: "Compensation", value: formatSalary(job) },
    { label: "Posted", value: formatPostedDate(job.posting_date) },
  ];

  // AJI-028: a closing date only when the provider stated one. Most
  // sources never do, so its absence is not shown as "Not stated".
  const closes = formatPostedDate(job.expires_at ?? null);
  if (closes) {
    facts.push({ label: "Closes", value: closes });
  }

  // Contract specifics only mean something on a contract role; on any
  // other role they are not "missing", just not applicable.
  if (job.employment_type === "contract") {
    facts.push(
      { label: "Contract length", value: job.contract_duration },
      {
        label: "Worker type",
        value: job.contract_worker_type
          ? formatValue(job.contract_worker_type)
          : null,
      },
    );
  }

  if (job.source_job_id) {
    facts.push({ label: "Source job ID", value: job.source_job_id });
  }

  const sections = [
    { label: "Description", text: job.description },
    { label: "Requirements", text: job.requirements },
    { label: "Responsibilities", text: job.responsibilities },
  ].filter((section) => section.text);

  return (
    <section
      aria-label="Job details"
      className="rounded-lg border border-app-border bg-app-bg p-4 sm:p-5"
    >
      <div className="font-mono text-[9px] uppercase tracking-[0.18em] text-app-blue">
        Job Details
      </div>
      <p className="mt-1 text-xs leading-5 text-app-faint">
        As provided by the job source. Anything the source didn&apos;t state
        is marked, never guessed.
      </p>

      <dl className="mt-4 grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
        {facts.map((fact) => (
          <div key={fact.label} className="min-w-0">
            <dt className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-faint">
              {fact.label}
            </dt>
            <dd
              className={
                fact.value
                  ? "mt-1 break-words text-sm font-medium text-app-text"
                  : "mt-1 text-sm italic text-app-faint"
              }
            >
              {fact.value || NOT_STATED}
            </dd>
          </div>
        ))}
      </dl>

      {sections.length > 0 ? (
        <div className="mt-5 space-y-5 border-t border-app-border pt-5">
          {sections.map((section) => (
            <div key={section.label}>
              <h4 className="font-mono text-[9px] uppercase tracking-[0.18em] text-app-blue">
                {section.label}
              </h4>
              <p className="mt-2 max-w-4xl whitespace-pre-line break-words text-sm leading-6 text-app-body">
                {section.text}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-5 border-t border-app-border pt-5 text-sm italic text-app-faint">
          The source didn&apos;t provide a description for this job.
        </p>
      )}
    </section>
  );
}
