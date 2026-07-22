export type IconName =
  | "jobs"
  | "approvals"
  | "companies"
  | "insights"
  | "profiles"
  | "targeting"
  | "candidate"
  | "dashboard"
  | "settings";

export type NavItem = {
  id: string;
  label: string;
  href: string;
  icon: IconName;
};
export type NavSection = { section: string };
export type NavEntry = NavSection | NavItem;

export const NAV: NavEntry[] = [
  { section: "Pipeline" },
  { id: "jobs", label: "Jobs", href: "/jobs", icon: "jobs" },
  {
    id: "approvals",
    label: "Approval queue",
    href: "/approvals",
    icon: "approvals",
  },
  {
    id: "companies",
    label: "Companies",
    href: "/companies",
    icon: "companies",
  },
  { section: "Intelligence" },
  { id: "insights", label: "Insights", href: "/insights", icon: "insights" },
  {
    id: "dashboard",
    label: "Dashboard",
    href: "/dashboard",
    icon: "dashboard",
  },
  { section: "Configure" },
  {
    id: "profiles",
    label: "Search profiles",
    href: "/profiles",
    icon: "profiles",
  },
  {
    id: "targeting",
    label: "Targeting",
    href: "/targeting",
    icon: "targeting",
  },
  { id: "settings", label: "Settings", href: "/settings", icon: "settings" },
];

/** A nav item is active when the current pathname equals its href or is nested under it. */
export function isActive(href: string, pathname: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
