"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getCurrentUser, logout } from "@/lib/auth";

export default function DashboardHeader() {

  const router = useRouter();
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
  return (
    <header className="flex items-center justify-between border-b border-[#1A3048] bg-[#05070A] px-5 py-4 md:px-8 lg:px-10">
      <div className="font-mono text-[10px] uppercase tracking-[0.25em] text-[#5E7187]">
        Command Center
      </div>

      <div className="flex items-center gap-5">
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-[#1677E8] shadow-[0_0_8px_rgba(22,119,232,0.8)]" />
          <span className="font-mono text-[10px] uppercase tracking-wider text-[#8D9AAA]">
            Session Active
          </span>
        </div>

        <div className="hidden text-sm text-[#F2F5F8] sm:block">{email}</div>

        <button
          type="button"
          onClick={handleLogout}
          className="border border-[#1A3048] px-4 py-2 text-xs font-semibold uppercase tracking-wider text-[#8D9AAA] transition hover:border-[#E50920] hover:text-[#F2F5F8]"
        >
          Logout
        </button>
      </div>
    </header>
  );
}
