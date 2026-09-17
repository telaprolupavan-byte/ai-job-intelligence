"use client";

import { Dialog } from "@base-ui/react/dialog";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import { primaryNavItems, secondaryNavItems } from "@/lib/nav-items";

export default function MobileNav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger
        className="app-focus-ring flex h-10 w-10 items-center justify-center border border-app-border text-app-muted transition hover:border-app-border-strong hover:text-app-text lg:hidden"
        aria-label="Open navigation menu"
      >
        <Menu className="h-5 w-5" aria-hidden="true" />
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-40 bg-black/60 transition-opacity duration-200 data-[starting-style]:opacity-0 data-[ending-style]:opacity-0 lg:hidden" />

        <Dialog.Popup
          className="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col border-r border-app-border bg-app-bg outline-none transition-transform duration-200 data-[open]:translate-x-0 data-[starting-style]:-translate-x-full data-[ending-style]:-translate-x-full data-[closed]:-translate-x-full lg:hidden"
        >
          <div className="flex items-center justify-between border-b border-app-border px-5 py-5">
            <Dialog.Title className="font-mono text-xs tracking-[0.2em] text-app-blue">
              AI / JOB INTELLIGENCE
            </Dialog.Title>

            <Dialog.Close
              className="app-focus-ring flex h-8 w-8 items-center justify-center text-app-muted transition hover:text-app-text"
              aria-label="Close navigation menu"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </Dialog.Close>
          </div>

          <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-5">
            {primaryNavItems.map((item) => {
              const active = pathname === item.href;
              const Icon = item.icon;

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  aria-current={active ? "page" : undefined}
                  className={`app-focus-ring flex items-center gap-3 px-3 py-3 text-sm transition ${
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
          </nav>

          <div className="border-t border-app-border px-3 py-4">
            {secondaryNavItems.map((item) => {
              const Icon = item.icon;

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className="app-focus-ring flex items-center gap-3 px-3 py-3 text-sm text-app-muted transition hover:text-app-text"
                >
                  <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                  {item.label}
                </Link>
              );
            })}
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
