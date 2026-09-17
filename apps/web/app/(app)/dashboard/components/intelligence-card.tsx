import Link from "next/link";

type Props = {
  label: string;
  value: string;
  detail: string;
  accent?: "red" | "blue";
  href?: string;
};

export default function IntelligenceCard({
  label,
  value,
  detail,
  accent = "red",
  href,
}: Props) {
  const accentClass = accent === "red" ? "text-app-red" : "text-app-blue";

  const content = (
    <>
      <div
        aria-hidden="true"
        className="absolute right-0 top-0 h-16 w-16 translate-x-8 -translate-y-8 rounded-full bg-app-blue/10 blur-2xl transition group-hover:bg-app-blue/20"
      />

      <div className="relative">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-app-soft">
          {label}
        </div>

        <div className={`mt-5 text-3xl font-bold tracking-tight ${accentClass}`}>
          {value}
        </div>

        <div className="mt-2 font-mono text-[9px] uppercase tracking-wider text-app-faint">
          {detail}
        </div>
      </div>
    </>
  );

  const className =
    "app-focus-ring group relative block overflow-hidden border border-app-border bg-app-panel p-5 transition hover:border-app-border-strong";

  if (href) {
    return (
      <Link href={href} className={className}>
        {content}
      </Link>
    );
  }

  return <div className={className}>{content}</div>;
}
