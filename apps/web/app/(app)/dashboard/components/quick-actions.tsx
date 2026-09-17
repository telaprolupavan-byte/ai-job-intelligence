import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { UploadCloud, ClipboardList, Briefcase, ListChecks } from "lucide-react";

const actions: {
  label: string;
  href: string;
  icon: LucideIcon;
  accent: "red" | "blue";
}[] = [
  {
    label: "Upload / Update Resume",
    href: "/resume",
    icon: UploadCloud,
    accent: "red",
  },
  {
    label: "Check ATS",
    href: "/ats",
    icon: ClipboardList,
    accent: "blue",
  },
  {
    label: "View Jobs",
    href: "/jobs",
    icon: Briefcase,
    accent: "blue",
  },
  {
    label: "Applications",
    href: "/applications",
    icon: ListChecks,
    accent: "red",
  },
];

export default function QuickActions() {
  return (
    <section aria-labelledby="quick-actions-heading">
      <div
        id="quick-actions-heading"
        className="mb-4 font-mono text-[10px] uppercase tracking-[0.25em] text-app-faint"
      >
        Quick Actions
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {actions.map((action) => {
          const Icon = action.icon;

          return (
            <Link
              key={action.label}
              href={action.href}
              className={`app-focus-ring flex items-center justify-between gap-3 rounded-lg border p-4 text-xs uppercase tracking-wider transition ${
                action.accent === "red"
                  ? "border-app-red-soft bg-app-red-soft/10 text-app-text hover:border-app-red hover:bg-app-red/10"
                  : "border-app-border bg-app-panel-strong text-app-muted hover:border-app-blue hover:text-app-text"
              }`}
            >
              <span className="flex items-center gap-2.5">
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                {action.label}
              </span>
              <span aria-hidden="true">→</span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
