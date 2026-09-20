"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X } from "lucide-react";

const NAV_LINKS = [
  { href: "#system", label: "Features" },
  { href: "#how-it-works", label: "How It Works" },
  { href: "#pricing", label: "Pricing" },
  { href: "#resources", label: "Resources" },
];

export default function LandingNav() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <div className="hidden items-center gap-9 lg:flex">
        {NAV_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="app-focus-ring text-sm text-app-body transition hover:text-app-text"
          >
            {link.label}
          </Link>
        ))}
      </div>

      <button
        type="button"
        aria-expanded={open}
        aria-controls="landing-mobile-menu"
        aria-label={open ? "Close navigation menu" : "Open navigation menu"}
        onClick={() => setOpen((v) => !v)}
        className="app-focus-ring flex h-9 w-9 items-center justify-center rounded-lg text-app-body transition hover:text-app-text lg:hidden"
      >
        {open ? (
          <X className="h-5 w-5" aria-hidden="true" />
        ) : (
          <Menu className="h-5 w-5" aria-hidden="true" />
        )}
      </button>

      {open && (
        <div
          id="landing-mobile-menu"
          className="absolute inset-x-0 top-full z-40 border-b border-white/10 bg-app-bg/95 backdrop-blur-md lg:hidden"
        >
          <nav className="flex flex-col gap-1 px-6 py-4">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className="app-focus-ring rounded-lg px-2 py-2.5 text-sm text-app-body transition hover:bg-white/[0.04] hover:text-app-text"
              >
                {link.label}
              </Link>
            ))}
            <Link
              href="/login"
              onClick={() => setOpen(false)}
              className="app-focus-ring rounded-lg px-2 py-2.5 text-sm text-app-body transition hover:bg-white/[0.04] hover:text-app-text"
            >
              Sign in
            </Link>
          </nav>
        </div>
      )}
    </>
  );
}
