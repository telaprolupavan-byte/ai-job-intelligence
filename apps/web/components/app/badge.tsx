import { cn } from "@/lib/utils";

type BadgeProps = {
  children: React.ReactNode;
  tone?:
    | "neutral"
    | "blue"
    | "red"
    | "amber"
    | "success"
    | "critical"
    | "danger"
    | "blue-soft"
    | "red-soft"
    | "success-soft"
    | "neutral-soft";
  className?: string;
};

// Filled, fully-rounded pill chips — matches the NERO Figma Job Card /
// Type / Match tag treatment (verified against nodes 34:87, 34:104,
// 34:121). Text color per tone is chosen for WCAG AA contrast (4.5:1,
// these are small ~10px labels so the "large text" 3:1 exception doesn't
// apply): app-blue/app-amber/app-success/app-critical are all too bright
// for light text at this size, so they pair with black text instead —
// the same reasoning documented on AppButton's crimson-fill, applied per
// tone here rather than deepening every fill color.
const TONE_CLASS = {
  neutral: "bg-app-panel-strong text-app-body",
  blue: "bg-app-blue text-black",
  red: "bg-crimson-fill text-white",
  // Reserved for predictive/warning states (Spider-Sense) — only ever
  // paired with real data, never shown speculatively.
  amber: "bg-app-amber text-black",
  success: "bg-app-success text-black",
  critical: "bg-app-critical text-black",
  // Distinct pre-existing alert treatment (used for e.g. ineligible
  // status) — kept as-is; no Figma reference confirms it should switch
  // to a solid fill, so only its shape is unified with the other tones.
  danger: "border border-app-danger-border bg-app-danger-bg text-app-danger-text",
  // "Soft" pills — desaturated background + colored text, matching the
  // NERO Dashboard — Desktop Figma (node 33:3) status pill treatment
  // (Resume readiness, Validation, Resume Analysis status chips).
  "blue-soft": "bg-app-blue-soft text-app-blue",
  "red-soft": "bg-app-red-soft text-app-red",
  "success-soft": "bg-app-success-soft text-app-success",
  "neutral-soft": "border border-app-border bg-app-surface text-app-muted",
};

export default function Badge({
  children,
  tone = "neutral",
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-3 py-1 font-mono text-[10px] font-semibold uppercase tracking-[0.06em]",
        TONE_CLASS[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
