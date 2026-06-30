import Link from "next/link";
import { NAV, type NavItem } from "@/lib/nav";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid h-screen grid-cols-[236px_1fr] overflow-hidden">
      <aside className="flex flex-col overflow-hidden border-r border-rule bg-panel">
        <div className="border-b border-rule px-5 pb-4 pt-[22px]">
          <span className="font-display text-[23px] font-semibold tracking-[0.05em] text-ink">
            Specula
          </span>
        </div>
        <nav className="flex-1 overflow-y-auto p-[14px_12px]">
          {NAV.map((entry, i) =>
            "section" in entry ? (
              <div
                key={`s${i}`}
                className="font-mono px-[10px] pb-[7px] pt-[14px] text-[9.5px] uppercase tracking-[0.16em] text-ink-3"
              >
                {entry.section}
              </div>
            ) : (
              <Link
                key={(entry as NavItem).id}
                href={(entry as NavItem).href}
                className="flex items-center gap-[10px] rounded-lg px-[11px] py-[9px] text-[13.5px] font-medium text-ink-2 hover:bg-panel-2 hover:text-ink"
              >
                {(entry as NavItem).label}
              </Link>
            ),
          )}
        </nav>
      </aside>
      <main className="main-scroll relative overflow-y-auto">{children}</main>
    </div>
  );
}
