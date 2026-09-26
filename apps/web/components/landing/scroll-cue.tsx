import { ChevronDown, Mouse } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * The page's scroll affordance, in one place.
 *
 * The same mono label + mouse + animated chevron used to be hand-copied
 * into the foot of the Hero, the System section, Discover Jobs and Job
 * Intelligence — four identical cues on one page, which is most of what
 * made the scroll read as a template. It now lives here and is used
 * where a cue genuinely helps: once in the hero, and once on the
 * Discover -> Job Intelligence hand-off, which is also a real anchor
 * link.
 */
export default function ScrollCue({
  label = "SCROLL TO EXPLORE",
  className,
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center gap-1.5", className)}>
      <span className="mono text-[9px] tracking-[0.3em] text-app-muted">
        {label}
      </span>
      <Mouse className="h-4 w-4 text-app-soft" aria-hidden="true" />
      <ChevronDown
        className="scroll-dot -mt-1 h-3 w-3 text-app-soft"
        aria-hidden="true"
      />
    </div>
  );
}
