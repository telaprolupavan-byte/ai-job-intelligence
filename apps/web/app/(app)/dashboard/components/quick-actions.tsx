import Link from "next/link";

const actions = [
  {
    label: "Upload / Update Resume",
    href: "/resume",
    accent: "red",
  },
  {
    label: "Check ATS",
    href: "/ats",
    accent: "blue",
  },
  {
    label: "View Jobs",
    href: "/jobs",
    accent: "blue",
  },
  {
    label: "Applications",
    href: "/applications",
    accent: "red",
  },
];

export default function QuickActions() {
  return (
    <section>
      <div className="mb-4 font-mono text-[10px] uppercase tracking-[0.25em] text-[#5E7187]">
        Quick Actions
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {actions.map((action) => (
          <Link
            key={action.label}
            href={action.href}
            className={`border p-4 text-xs uppercase tracking-wider transition ${
              action.accent === "red"
                ? "border-[#8B0B18] bg-[#8B0B18]/10 text-[#F2F5F8] hover:border-[#E50920] hover:bg-[#E50920]/10"
                : "border-[#1A3048] bg-[#07111F] text-[#8D9AAA] hover:border-[#1677E8] hover:text-[#F2F5F8]"
            }`}
          >
            {action.label}
            <span className="float-right">→</span>
          </Link>
        ))}
      </div>
    </section>
  );
}