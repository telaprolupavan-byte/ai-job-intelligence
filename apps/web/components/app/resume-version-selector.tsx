"use client";

import { Select } from "@base-ui/react/select";
import { AlertTriangle, Check, ChevronDown, FileText } from "lucide-react";
import AppButton from "./app-button";
import EmptyState from "./empty-state";
import { Skeleton } from "./skeleton";

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
   * The option that today's backend default (most recent resume,
   * preferring its master version) would resolve to. Used to label the
   * trigger before the user has made an explicit choice.
   */
  defaultOptionId: string | null;
  /**
   * null means "no explicit choice yet" - resume_version_id stays
   * omitted from Match/ATS/Gap Analysis requests and the backend's own
   * default applies, unchanged.
   */
  selectedId: string | null;
  onSelect: (id: string) => void;
  errorMessage?: string;
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

export default function ResumeVersionSelector({
  status,
  options,
  defaultOptionId,
  selectedId,
  onSelect,
  errorMessage,
  onRetry,
}: ResumeVersionSelectorProps) {
  const labelId = "resume-version-selector-label";

  if (status === "loading") {
    return (
      <div role="status" aria-live="polite" className="w-full sm:max-w-[420px]">
        <span className="sr-only">Loading your resume versions…</span>
        <Skeleton className="h-[52px] w-full rounded-lg" />
      </div>
    );
  }

  if (status === "error") {
    return (
      <div
        role="alert"
        className="w-full rounded-lg border border-app-danger-border bg-app-danger-bg px-4 py-3 sm:max-w-[420px]"
      >
        <div className="flex items-center gap-2">
          <AlertTriangle
            className="h-4 w-4 shrink-0 text-app-red"
            aria-hidden="true"
          />
          <span className="text-sm font-medium text-app-danger-text">
            Resume versions unavailable
          </span>
        </div>

        {errorMessage && (
          <p className="mt-1 text-xs leading-5 text-app-danger-text">
            {errorMessage}
          </p>
        )}

        <p className="mt-1 text-xs leading-5 text-app-danger-text">
          Match, ATS, and Gap Analysis will keep using your default resume
          until this loads.
        </p>

        <div className="mt-3">
          <AppButton variant="secondary" size="sm" onClick={onRetry}>
            Retry
          </AppButton>
        </div>
      </div>
    );
  }

  if (status === "empty" || options.length === 0) {
    return (
      <div className="w-full sm:max-w-[420px]">
        <EmptyState
          icon={FileText}
          title="No resume on file"
          description="Upload a resume so NERO knows what to use for Match, ATS, and Gap Analysis."
          action={
            <AppButton variant="secondary" size="sm" href="/resume">
              Go to Resume
            </AppButton>
          }
        />
      </div>
    );
  }

  const effectiveId = selectedId ?? defaultOptionId;
  const isUsingDefault = selectedId === null;
  const activeOption = options.find((option) => option.id === effectiveId);

  return (
    <Select.Root
      value={effectiveId}
      onValueChange={(value) => {
        if (typeof value === "string") {
          onSelect(value);
        }
      }}
    >
      <Select.Trigger
        aria-labelledby={labelId}
        className="app-focus-ring flex w-full items-center gap-3 rounded-lg border border-app-border-strong bg-app-panel px-4 py-3 text-left text-sm text-app-text outline-none transition-colors hover:border-app-blue sm:max-w-[420px]"
      >
        <FileText
          className="h-4 w-4 shrink-0 text-app-muted"
          aria-hidden="true"
        />

        <span className="min-w-0 flex-1">
          <Select.Value>
            {() => (
              <span className="block min-w-0">
                <span className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium text-app-text">
                    {activeOption?.resumeName ?? "Select a resume"}
                  </span>
                  {isUsingDefault && (
                    <span className="shrink-0 font-mono text-[8px] uppercase tracking-[0.12em] text-app-faint">
                      Default
                    </span>
                  )}
                </span>
                {activeOption && (
                  <span className="mt-0.5 block truncate font-mono text-[9px] uppercase tracking-[0.1em] text-app-faint">
                    {activeOption.versionName}
                    {activeOption.isMaster ? " · Master" : ""}
                    {" · "}
                    {formatDate(activeOption.createdAt)}
                  </span>
                )}
              </span>
            )}
          </Select.Value>
        </span>

        <Select.Icon className="shrink-0 text-app-muted">
          <ChevronDown className="h-4 w-4" aria-hidden="true" />
        </Select.Icon>
      </Select.Trigger>

      <Select.Portal>
        <Select.Positioner
          className="z-50 outline-none"
          sideOffset={8}
          collisionPadding={16}
        >
          <Select.Popup className="max-h-80 w-[var(--anchor-width)] overflow-auto rounded-lg border border-app-border-strong bg-app-panel-strong py-1 shadow-lg outline-none">
            <Select.List>
              {options.map((option) => (
                <Select.Item
                  key={option.id}
                  value={option.id}
                  className="app-focus-ring flex cursor-pointer items-center justify-between gap-3 px-4 py-3 outline-none data-[highlighted]:bg-app-panel data-[selected]:bg-app-blue/5"
                >
                  <span className="min-w-0">
                    <Select.ItemText className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium text-app-text">
                        {option.resumeName}
                      </span>
                      {option.isMaster && (
                        <span className="shrink-0 rounded-full bg-app-blue-soft px-2 py-0.5 font-mono text-[8px] uppercase tracking-[0.1em] text-app-blue">
                          Master
                        </span>
                      )}
                    </Select.ItemText>
                    <span className="mt-0.5 block truncate font-mono text-[9px] uppercase tracking-[0.1em] text-app-faint">
                      {option.versionName} · {formatDate(option.createdAt)}
                    </span>
                  </span>

                  <Select.ItemIndicator className="shrink-0 text-app-blue">
                    <Check className="h-4 w-4" aria-hidden="true" />
                  </Select.ItemIndicator>
                </Select.Item>
              ))}
            </Select.List>
          </Select.Popup>
        </Select.Positioner>
      </Select.Portal>
    </Select.Root>
  );
}
