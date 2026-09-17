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
    <div>
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-app-soft">
        {label}
      </div>

      <div className={`mt-4 text-2xl font-bold tracking-tight ${accentClass}`}>
        {value}
      </div>

      <div className="mt-2 font-mono text-[9px] uppercase tracking-wider text-app-faint">
        {detail}
      </div>
    </div>
  );

  const className =
    "app-focus-ring group block rounded-xl border border-app-border bg-app-panel p-5 transition hover:border-app-border-strong";

  if (href) {
    return (
      <Link href={href} className={className}>
        {content}
      </Link>
    );
  }

  return <div className={className}>{content}</div>;
}
