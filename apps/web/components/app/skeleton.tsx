import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={cn("app-skeleton rounded-lg", className)}
    />
  );
}

export function PanelSkeleton({
  lines = 3,
  className,
}: {
  lines?: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-app-border bg-app-panel p-5",
        className,
      )}
    >
      <Skeleton className="h-3 w-24" />
      <Skeleton className="mt-4 h-6 w-3/4" />
      <div className="mt-4 space-y-2">
        {Array.from({ length: lines }).map((_, index) => (
          <Skeleton key={index} className="h-3 w-full" />
        ))}
      </div>
    </div>
  );
}
