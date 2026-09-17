"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { LogOut } from "lucide-react";
import { getCurrentUser, logout } from "@/lib/auth";
import { primaryNavItems, secondaryNavItems } from "@/lib/nav-items";
import MobileNav from "@/components/app/mobile-nav";

const allNavItems = [...primaryNavItems, ...secondaryNavItems];

export default function DashboardHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const [email, setEmail] = useState("");

  useEffect(() => {
    getCurrentUser()
      .then((user) => {
        setEmail(user.email);
      })
      .catch(() => {
        setEmail("");
      });
  }, []);

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  const currentLabel =
    allNavItems.find((item) => item.href === pathname)?.label ??
    "Command Center";

  return (
    <header className="flex items-center justify-between border-b border-app-border bg-app-bg px-5 py-4 md:px-8 lg:px-10">
      <div className="flex items-center gap-4">
        <MobileNav />

        <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-app-faint">
          {currentLabel}
        </div>
      </div>

      <div className="flex items-center gap-3 sm:gap-5">
        <div className="hidden items-center gap-2 sm:flex">
          <span
            aria-hidden="true"
            className="h-1.5 w-1.5 rounded-full bg-app-blue shadow-[0_0_8px_rgba(22,119,232,0.8)]"
          />
          <span className="font-mono text-[10px] uppercase tracking-wider text-app-muted">
            Session Active
          </span>
        </div>

        <div className="hidden max-w-[16rem] truncate text-sm text-app-text sm:block">
          {email}
        </div>

        <button
          type="button"
          onClick={handleLogout}
          className="app-focus-ring flex items-center gap-2 border border-app-border px-4 py-2 text-xs font-semibold uppercase tracking-wider text-app-muted transition hover:border-app-red hover:text-app-text"
        >
          <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="hidden sm:inline">Logout</span>
        </button>
      </div>
    </header>
  );
}
