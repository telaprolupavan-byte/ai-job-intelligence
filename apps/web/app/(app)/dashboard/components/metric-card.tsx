import Link from "next/link";
import Panel from "@/components/app/panel";
import { cn } from "@/lib/utils";

type Accent = "blue" | "red" | "amber" | "success";

const ACCENT_CLASS: Record<Accent, string> = {
  blue: "bg-app-blue-soft",
  red: "bg-app-red-soft",
  amber: "bg-app-amber-soft",
  success: "bg-app-success-soft",
};

type Props = {
  label: string;
  value: React.ReactNode;
  meta: string;
  accent: Accent;
  href?: string;
};

export default function MetricCard({ label, value, meta, accent, href }: Props) {
  const content = (
    <>
      <div className="flex items-start justify-between gap-3">
        <div className="text-xs text-app-muted">{label}</div>
        <div
          aria-hidden="true"
          className={cn("h-7 w-7 shrink-0 rounded-[14px]", ACCENT_CLASS[accent])}
        />
      </div>

      <div className="mt-4 text-[28px] font-bold leading-none text-app-text">
        {value}
      </div>

      <div className="mt-3 text-xs text-app-faint">{meta}</div>
    </>
  );

  if (href) {
    return (
      <Link
        href={href}
        className="app-focus-ring block rounded-xl border border-app-border bg-app-panel p-5 transition hover:border-app-border-strong"
      >
        {content}
      </Link>
    );
  }

  return <Panel>{content}</Panel>;
}
