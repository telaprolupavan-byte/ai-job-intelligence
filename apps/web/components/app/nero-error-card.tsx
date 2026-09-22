import { cn } from "@/lib/utils";

// NERO / Empty & Error, State=Error (Figma component 25:62) — "resilient
// empty and failure states for intelligence surfaces". A deliberately
// light card on the dark app surface, so its colors are the component's
// own values rather than app-* tokens (the palette has no light-surface
// equivalents).

type NeroErrorCardProps = {
  title?: string;
  message?: string;
  className?: string;
};

export default function NeroErrorCard({
  title = "Analysis unavailable",
  message = "Something went wrong. Retry when the service is available.",
  className,
}: NeroErrorCardProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-start gap-2 rounded-2xl border border-[#db2626] bg-white px-6 py-[22px]",
        className,
      )}
    >
      <p className="text-lg font-semibold text-[#05060a]">{title}</p>
      <p className="font-[family-name:var(--font-instrument-sans)] text-sm text-[#4d576b]">
        {message}
      </p>
    </div>
  );
}
