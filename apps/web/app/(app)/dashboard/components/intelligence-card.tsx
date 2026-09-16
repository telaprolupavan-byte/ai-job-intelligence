type Props = {
  label: string;
  value: string;
  detail: string;
  accent?: "red" | "blue";
};

export default function IntelligenceCard({
  label,
  value,
  detail,
  accent = "red",
}: Props) {
  const accentClass =
    accent === "red" ? "text-[#E50920]" : "text-[#1677E8]";

  return (
    <div className="group relative overflow-hidden border border-[#1A3048] bg-[#0B1626] p-5 transition hover:border-[#294B70]">
      <div className="absolute right-0 top-0 h-16 w-16 translate-x-8 -translate-y-8 rounded-full bg-[#1677E8]/10 blur-2xl transition group-hover:bg-[#1677E8]/20" />

      <div className="relative">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#71849A]">
          {label}
        </div>

        <div className={`mt-5 text-3xl font-bold tracking-tight ${accentClass}`}>
          {value}
        </div>

        <div className="mt-2 font-mono text-[9px] uppercase tracking-wider text-[#5E7187]">
          {detail}
        </div>
      </div>
    </div>
  );
}