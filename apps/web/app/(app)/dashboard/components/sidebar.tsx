"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { primaryNavItems, secondaryNavItems } from "@/lib/nav-items";
import NeroBrand from "@/components/app/nero-brand";

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-72 shrink-0 overflow-y-auto border-r border-app-border bg-app-panel lg:fixed lg:inset-y-0 lg:left-0 lg:z-30 lg:flex lg:flex-col">
      <div className="border-b border-app-border px-6 py-7">
        <NeroBrand />
      </div>

      <nav className="flex-1 px-6 py-6" aria-label="Primary">
        <div className="mb-4 font-mono text-[10px] uppercase tracking-[0.25em] text-app-faint">
          Navigation
        </div>

        <div className="space-y-1">
          {primaryNavItems.map((item) => {
            const active = pathname === item.href;
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`app-focus-ring group flex h-[42px] items-center gap-3 rounded-lg px-4 text-sm transition ${
                  active
                    ? "bg-app-red text-white"
                    : "bg-transparent text-app-body hover:bg-app-panel-strong hover:text-app-text"
                }`}
              >
                <Icon
                  className={`h-4 w-4 shrink-0 ${active ? "text-white" : "text-app-faint group-hover:text-app-muted"}`}
                  aria-hidden="true"
                />

                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>

      <div className="border-t border-app-border p-3">
        {secondaryNavItems.map((item) => {
          const active = pathname === item.href;
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`app-focus-ring flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition ${
                active
                  ? "bg-app-panel text-app-text"
                  : "text-app-muted hover:bg-app-panel-strong hover:text-app-text"
              }`}
            >
              <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
              {item.label}
            </Link>
          );
        })}
      </div>
    </aside>
  );
}
