import { cn } from "@/lib/utils";

type BadgeProps = {
  children: React.ReactNode;
  tone?: "neutral" | "blue" | "red" | "danger";
  className?: string;
};

const TONE_CLASS = {
  neutral: "border-app-border bg-app-surface text-app-muted",
  blue: "border-app-blue/60 text-app-blue",
  red: "border-app-red/60 text-app-red",
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
        "inline-flex items-center border px-3 py-1.5 font-mono text-[9px] uppercase tracking-[0.1em]",
        TONE_CLASS[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
