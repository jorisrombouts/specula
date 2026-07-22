import type { IconName } from "@/lib/nav";

const PATHS: Record<IconName, string> = {
  jobs: "M2 3h12M2 8h12M2 13h8",
  approvals: "M3 8l3.5 3.5L13 4",
  companies:
    "M2.5 14V5l5-2.5L12.5 5v9M5.5 8h0.5M5.5 11h0.5M9.5 8h0.5M9.5 11h0.5",
  insights: "M2 14V2M2 14h12M5 11l3-4 2 2 3-5",
  profiles: "M3 4h10M5 8h8M7 12h6",
  candidate:
    "M8 8.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM3 14c0-2.5 2.2-4 5-4s5 1.5 5 4",
  targeting:
    "M8 14A6 6 0 108 2a6 6 0 000 12zM8 11a3 3 0 100-6 3 3 0 000 6zM8 8h0.01",
};

export function Icon({ name }: { name: IconName }) {
  return (
    <svg
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-full w-full"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
