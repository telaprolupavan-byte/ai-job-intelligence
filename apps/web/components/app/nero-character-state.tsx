import { cn } from "@/lib/utils";

// NERO / Character State (Figma component 25:50) — "visual companion
// states used to communicate AI workflow status without turning NERO into
// a chatbot". Only the states a shipped screen actually uses are
// implemented; the other Figma variants (Thinking, Searching) are added
// when a screen needs them. Success (reference 68:56) is used by the
// AJI-023 job decision panel once its analyses have all completed.
//
// The avatar is the design's own placeholder — a solid Neural Blue disc
// (node 25:36) — drawn with the app-blue token; Success is the green
// disc, drawn with the app-success token.

export type NeroCharacterStateName = "Idle" | "Analyzing" | "Success";

type NeroCharacterStateProps = {
  state: NeroCharacterStateName;
  className?: string;
};

export default function NeroCharacterState({
  state,
  className,
}: NeroCharacterStateProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={`NERO: ${state}`}
      className={cn(
        "flex flex-col items-center gap-3 rounded-2xl bg-app-bg py-5",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "block size-[76px] shrink-0 rounded-full",
          state === "Success" ? "bg-app-success" : "bg-app-blue",
        )}
      />
      <p className="whitespace-nowrap text-sm font-semibold text-app-text">
        {state}
      </p>
    </div>
  );
}
