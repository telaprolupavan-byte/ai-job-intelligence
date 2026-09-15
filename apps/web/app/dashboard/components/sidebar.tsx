"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navigation = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Jobs", href: "/jobs" },
  { label: "Applications", href: "/applications" },
  { label: "Resume", href: "/resume" },
  { label: "ATS Analysis", href: "/ats" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden min-h-screen w-64 shrink-0 border-r border-[#1A3048] bg-[#05070A] lg:flex lg:flex-col">
      <div className="border-b border-[#1A3048] px-6 py-7">
        <Link href="/" className="block">
          <div className="font-mono text-xs tracking-[0.25em] text-[#1677E8]">
            AI / JOB
          </div>

          <div className="mt-1 text-xl font-bold tracking-tight text-[#F2F5F8]">
            INTELLIGENCE
          </div>
        </Link>
      </div>

      <nav className="flex-1 px-3 py-8">
        <div className="mb-4 px-3 font-mono text-[10px] uppercase tracking-[0.25em] text-[#5E7187]">
          Command Center
        </div>

        <div className="space-y-1">
          {navigation.map((item) => {
            const active = pathname === item.href;

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`group relative flex items-center gap-3 px-3 py-3 text-sm transition ${
                  active
                    ? "bg-[#0B1626] text-[#F2F5F8]"
                    : "text-[#8D9AAA] hover:bg-[#07111F] hover:text-[#F2F5F8]"
                }`}
              >
                {active && (
                  <span className="absolute left-0 top-0 h-full w-[3px] bg-[#E50920]" />
                )}

                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    active ? "bg-[#E50920]" : "bg-[#29425F]"
                  }`}
                />

                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>

      <div className="border-t border-[#1A3048] p-5">
        <Link
          href="/settings"
          className="text-xs text-[#8D9AAA] transition hover:text-[#F2F5F8]"
        >
          Settings →
        </Link>
      </div>
    </aside>
  );
}