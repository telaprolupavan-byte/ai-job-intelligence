import { AlertTriangle } from "lucide-react";
import AppButton from "./app-button";

type ErrorStateProps = {
  title?: string;
  message: string;
  onRetry?: () => void;
  className?: string;
};

export default function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={`rounded-xl border border-app-danger-border bg-app-danger-bg p-5 ${className ?? ""}`}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle
          className="mt-0.5 h-4 w-4 shrink-0 text-app-red"
          aria-hidden="true"
        />

        <div className="min-w-0">
          <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-app-red">
            {title}
          </div>

          <p className="mt-2 text-sm leading-6 text-app-danger-text">
            {message}
          </p>

          {onRetry && (
            <div className="mt-4">
              <AppButton variant="secondary" size="sm" onClick={onRetry}>
                Try Again
              </AppButton>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
