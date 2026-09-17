import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Briefcase,
  ClipboardList,
  ListChecks,
  FileText,
  Settings,
} from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
};

// Every item here corresponds to a route that actually exists and is
// wired up today. Do not add entries for future/unbuilt features.
export const primaryNavItems: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Jobs", href: "/jobs", icon: Briefcase },
  { label: "Resume", href: "/resume", icon: FileText },
  { label: "ATS Analysis", href: "/ats", icon: ClipboardList },
  { label: "Applications", href: "/applications", icon: ListChecks },
];

export const secondaryNavItems: NavItem[] = [
  { label: "Settings", href: "/settings", icon: Settings },
];
