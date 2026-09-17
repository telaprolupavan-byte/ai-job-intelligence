import type { LucideIcon } from "lucide-react";
import { Inbox } from "lucide-react";

type EmptyStateProps = {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
};

export default function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={`border border-app-border bg-app-panel px-6 py-14 text-center ${className ?? ""}`}
    >
      <div className="mx-auto flex h-11 w-11 items-center justify-center border border-app-border-strong text-app-soft">
        <Icon className="h-5 w-5" aria-hidden="true" />
      </div>

      <h3 className="mt-5 text-lg font-semibold text-app-text">{title}</h3>

      {description && (
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-app-muted">
          {description}
        </p>
      )}

      {action && <div className="mt-6 flex justify-center">{action}</div>}
    </div>
  );
}
