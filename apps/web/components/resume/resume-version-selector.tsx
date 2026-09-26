"use client";

import { Select } from "@base-ui/react/select";
import { ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

// Implements NERO / Resume Version Selector (Figma file 8M2zzb8BtZyLmwcTGUle5l,
// node 60:8 - states 60:3..60:7) per AJI-019 — Selector Specification (61:36).
// Built on @base-ui/react's Select primitive per that spec's Builder Rule.

export type ResumeVersionOption = {
  id: string;
  resumeName: string;
  versionName: string;
  isMaster: boolean;
  createdAt: string;
};

type ResumeVersionSelectorProps = {
  status: "loading" | "error" | "empty" | "ready";
  options: ResumeVersionOption[];
  /**
   * The option today's backend default (most recent resume, preferring
   * its master version) would resolve to. Used to label the trigger
   * before the user has made an explicit choice.
   */
  defaultOptionId: string | null;
  /**
   * null means "no explicit choice yet" - resume_version_id stays
   * omitted from Match/ATS/Gap Analysis requests and the backend's own
   * default applies, unchanged.
   */
  selectedId: string | null;
  onSelect: (id: string) => void;
  onRetry: () => void;
};

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function versionLabel(option: ResumeVersionOption): string {
  return `${option.versionName}${option.isMaster ? " · Master" : ""} · ${formatDate(option.createdAt)}`;
}

const CONTAINER_CLASS =
  "flex w-full items-center gap-3 rounded-lg border border-app-border bg-app-panel px-4 py-2.5 sm:max-w-[420px]";

export default function ResumeVersionSelector({
  status,
  options,
  defaultOptionId,
  selectedId,
  onSelect,
  onRetry,
}: ResumeVersionSelectorProps) {
  const [open, setOpen] = useState(false);

  if (status === "loading") {
    return (
      <div
        role="status"
        aria-live="polite"
        className={CONTAINER_CLASS}
      >
        <Loader2
          className="h-4 w-4 shrink-0 animate-spin text-app-blue"
          aria-hidden="true"
        />
        <span className="min-w-0 flex-1">
          <span className="block font-mono text-[9px] font-medium uppercase tracking-[0.1em] text-app-muted">
            Resume Library
          </span>
          <span className="mt-0.5 block truncate text-sm font-semibold text-app-text">
            Loading your resume versions…
          </span>
        </span>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div role="alert" className={CONTAINER_CLASS}>
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-app-red">
          <span className="text-[15px] font-semibold text-app-text">!</span>
        </span>

        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold text-app-text">
            Resume versions unavailable
          </span>
          <span className="mt-0.5 block text-[10px] leading-4 text-app-muted">
            Try again or continue with your default resume.
          </span>
        </span>

        <button
          type="button"
          onClick={onRetry}
          className="app-focus-ring shrink-0 rounded px-2 py-2 text-[10px] font-semibold text-app-red hover:underline"
        >
          Retry
        </button>
      </div>
    );
  }

  if (status === "empty" || options.length === 0) {
    return (
      <div className={CONTAINER_CLASS}>
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-app-red">
          <span className="text-[16px] font-semibold text-app-text">+</span>
        </span>

        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold leading-5 text-app-text">
            Add a resume to use NERO Intelligence
          </span>
          <span className="mt-0.5 block text-[10px] leading-4 text-app-muted">
            Upload one from Resume to unlock version selection.
          </span>
        </span>

        <Link
          href="/resume"
          className="app-focus-ring shrink-0 rounded px-2 py-2 text-[10px] font-semibold text-app-red hover:underline"
        >
          Open Resume
        </Link>
      </div>
    );
  }

  const effectiveId = selectedId ?? defaultOptionId;
  const activeOption = options.find((option) => option.id === effectiveId);

  return (
    <Select.Root
      value={effectiveId}
      onValueChange={(value) => {
        if (typeof value === "string") {
          onSelect(value);
        }
      }}
      open={open}
      onOpenChange={setOpen}
    >
      <Select.Trigger className="app-focus-ring flex w-full items-center gap-3 rounded-lg border border-app-border bg-app-panel px-4 py-2.5 text-left outline-none transition-colors hover:border-app-blue sm:max-w-[420px]">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-app-blue">
          <span className="text-[11px] font-semibold text-app-text">CV</span>
        </span>

        <span className="min-w-0 flex-1">
          <span className="block font-mono text-[9px] font-medium uppercase tracking-[0.1em] text-app-muted">
            Using Resume
          </span>

          <Select.Value>
            {() => (
              <span className="block min-w-0">
                <span className="block truncate text-sm font-semibold text-app-text">
                  {activeOption?.resumeName ?? "Select a resume"}
                </span>
                {activeOption && (
                  <span className="mt-0.5 block truncate text-[11px] text-app-body">
                    {versionLabel(activeOption)}
                  </span>
                )}
              </span>
            )}
          </Select.Value>
        </span>

        {open ? (
          <ChevronUp
            className="h-5 w-5 shrink-0 text-app-muted"
            aria-hidden="true"
          />
        ) : (
          <ChevronDown
            className="h-5 w-5 shrink-0 text-app-muted"
            aria-hidden="true"
          />
        )}
      </Select.Trigger>

      <Select.Portal>
        <Select.Positioner
          className="z-50 outline-none"
          sideOffset={6}
          collisionPadding={16}
        >
          <Select.Popup className="max-h-80 w-[var(--anchor-width)] overflow-auto rounded-lg border border-app-border bg-app-panel p-1.5 shadow-lg outline-none">
            <Select.List>
              {options.map((option) => {
                const isSelected = option.id === effectiveId;

                if (isSelected) {
                  return (
                    <Select.Item
                      key={option.id}
                      value={option.id}
                      className="app-focus-ring flex cursor-pointer items-center gap-2 rounded-lg bg-app-blue px-3 py-2.5 outline-none"
                    >
                      <span
                        aria-hidden="true"
                        className="h-2 w-2 shrink-0 rounded-full bg-app-text"
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[11px] font-medium text-app-text">
                          {option.resumeName}
                        </span>
                        <span className="mt-0.5 block truncate text-[9px] text-app-text/80">
                          {versionLabel(option)}
                        </span>
                      </span>
                      <span className="shrink-0 text-[9px] font-semibold text-app-text">
                        Selected
                      </span>
                    </Select.Item>
                  );
                }

                return (
                  <Select.Item
                    key={option.id}
                    value={option.id}
                    className="app-focus-ring block cursor-pointer truncate rounded-lg px-4 py-2.5 text-[11px] font-medium text-app-text outline-none data-[highlighted]:bg-app-panel-strong"
                  >
                    {option.resumeName} · {versionLabel(option)}
                  </Select.Item>
                );
              })}
            </Select.List>
          </Select.Popup>
        </Select.Positioner>
      </Select.Portal>
    </Select.Root>
  );
}
