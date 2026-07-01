"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV, isActive, type NavItem } from "@/lib/nav";
import { Icon } from "@/components/icon";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex flex-col overflow-hidden border-r border-rule bg-panel">
      {/* Brand + inert sync/refresh */}
      <div className="border-b border-rule px-5 pb-4 pt-[22px]">
        <div className="flex items-baseline gap-2">
          <span className="font-display text-[23px] font-semibold tracking-[0.05em] text-ink">
            Specula
          </span>
          <span className="font-mono text-[10px] tracking-[0.02em] text-ink-2">
            role ledger
          </span>
        </div>
        <div className="mt-[14px] flex flex-col gap-[9px]">
          <div className="font-mono flex items-center gap-2 text-[11px] text-ink-2">
            <span className="sync-dot relative h-[7px] w-[7px] flex-shrink-0 rounded-full bg-accent" />
            synced <b className="font-semibold text-ink">—</b> ·{" "}
            <b className="font-semibold text-ink">—</b> new
          </div>
          <button
            type="button"
            disabled
            title="Available in a later milestone"
            className="font-body mt-1 flex w-full items-center justify-center gap-[7px] rounded-[7px] bg-ink px-3 py-[9px] text-[12.5px] font-semibold text-paper opacity-60"
          >
            <span aria-hidden>↻</span> Refresh now
          </button>
        </div>
      </div>

      {/* Nav */}
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
            <NavLink
              key={(entry as NavItem).id}
              item={entry as NavItem}
              pathname={pathname}
            />
          ),
        )}
      </nav>

      {/* Candidate card — neutral placeholder until M0b/M2 */}
      <div className="border-t border-rule p-3">
        <Link
          href="/candidate"
          aria-current={isActive("/candidate", pathname) ? "page" : undefined}
          className={`flex w-full items-center gap-[11px] rounded-[9px] border px-[10px] py-[9px] text-left ${
            isActive("/candidate", pathname)
              ? "border-rule bg-panel-2"
              : "border-transparent hover:border-rule hover:bg-panel-2"
          }`}
        >
          <span className="font-mono flex h-[34px] w-[34px] flex-shrink-0 items-center justify-center rounded-[9px] bg-ink text-[13px] font-semibold text-paper">
            <span className="h-[15px] w-[15px]">
              <Icon name="candidate" />
            </span>
          </span>
          <span>
            <span className="block text-[13px] font-semibold text-ink">
              Candidate
            </span>
            <span className="block text-[11.5px] text-ink-2">profile</span>
          </span>
        </Link>
      </div>
    </aside>
  );
}

function NavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const on = isActive(item.href, pathname);
  return (
    <Link
      href={item.href}
      aria-current={on ? "page" : undefined}
      className={`flex items-center gap-[10px] rounded-lg px-[11px] py-[9px] text-[13.5px] font-medium ${
        on ? "bg-ink text-paper" : "text-ink-2 hover:bg-panel-2 hover:text-ink"
      }`}
    >
      <span className="flex h-[15px] w-[15px] flex-shrink-0">
        <Icon name={item.icon} />
      </span>
      <span className="flex-1">{item.label}</span>
    </Link>
  );
}
