// AJI-028 — the visible source credit some job sources require as a
// condition of use ("Job via X", linking to the posting on X). Renders
// nothing unless the API says this job's source requires it, so jobs from
// sources without that obligation look exactly as before.

import type { Job } from "@/lib/jobs";
import { sourceAttributionLink } from "@/lib/job-format";

export default function SourceAttributionLink({ job }: { job: Job }) {
  const link = sourceAttributionLink(job);

  if (!link) return null;

  return (
    <a
      href={link.href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-mono text-[9px] uppercase tracking-[0.15em] text-app-blue underline underline-offset-2"
    >
      {link.label}
    </a>
  );
}
