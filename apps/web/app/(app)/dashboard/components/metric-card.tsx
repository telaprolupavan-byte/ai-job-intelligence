import Panel from "@/components/app/panel";
import { cn } from "@/lib/utils";

type Props = {
  label: string;
  value: string;
  caption: string;
  accent: "blue" | "red" | "amber" | "success";
};

const ACCENT_CLASS: Record<Props["accent"], string> = {
  blue: "bg-app-blue-soft",
  red: "bg-app-red-soft",
  amber: "bg-app-amber-soft",
  success: "bg-app-success-soft",
};

export default function MetricCard({ label, value, caption, accent }: Props) {
  return (
    <Panel as="div" padding="lg" className="relative">
      <div
        aria-hidden="true"
        className={cn(
          "absolute right-5 top-5 h-7 w-7 rounded-full",
          ACCENT_CLASS[accent],
        )}
      />

      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-app-muted">
        {label}
      </div>

      <div className="mt-3 text-[28px] font-bold leading-none tracking-tight text-app-text">
        {value}
      </div>

      <div className="mt-3 text-xs text-app-soft">{caption}</div>
    </Panel>
  );
}
