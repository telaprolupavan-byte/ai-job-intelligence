import { cn } from "@/lib/utils";

type PanelProps = {
  children: React.ReactNode;
  className?: string;
  padding?: "none" | "sm" | "md" | "lg";
  strong?: boolean;
  interactive?: boolean;
  as?: "div" | "section" | "article" | "form";
};

const PADDING_CLASS = {
  none: "",
  sm: "p-4",
  md: "p-5",
  lg: "p-6",
};

export default function Panel({
  children,
  className,
  padding = "md",
  strong = false,
  interactive = false,
  as = "section",
}: PanelProps) {
  const Tag = as;

  return (
    <Tag
      className={cn(
        "border border-app-border",
        strong ? "bg-app-panel-strong" : "bg-app-panel",
        PADDING_CLASS[padding],
        interactive &&
          "transition-colors hover:border-app-border-strong",
        className,
      )}
    >
      {children}
    </Tag>
  );
}

type PanelHeaderProps = {
  eyebrow: string;
  title?: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
};

export function PanelHeader({
  eyebrow,
  title,
  description,
  action,
  className,
}: PanelHeaderProps) {
  return (
    <div
      className={cn(
        "flex items-start justify-between gap-4 border-b border-app-border px-5 py-4",
        className,
      )}
    >
      <div className="min-w-0">
        <div className="font-mono text-[9px] uppercase tracking-[0.2em] text-app-blue">
          {eyebrow}
        </div>

        {title && (
          <h2 className="mt-1 text-lg font-semibold text-app-text">
            {title}
          </h2>
        )}

        {description && (
          <p className="mt-1 text-sm text-app-muted">{description}</p>
        )}
      </div>

      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
