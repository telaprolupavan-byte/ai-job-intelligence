import { cn } from "@/lib/utils";

type BadgeProps = {
  children: React.ReactNode;
  tone?: "neutral" | "blue" | "red" | "amber" | "success" | "critical" | "danger";
  className?: string;
};

const TONE_CLASS = {
  neutral: "border-app-border bg-app-surface text-app-muted",
  blue: "border-app-blue/60 text-app-blue",
  red: "border-app-red/60 text-app-red",
  // Reserved for predictive/warning states (Spider-Sense) — only ever
  // paired with real data, never shown speculatively.
  amber: "border-app-amber/60 text-app-amber",
  success: "border-app-success/60 text-app-success",
  critical: "border-app-critical/60 text-app-critical",
  danger: "border-app-danger-border bg-app-danger-bg text-app-danger-text",
};

export default function Badge({
  children,
  tone = "neutral",
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.08em]",
        TONE_CLASS[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
