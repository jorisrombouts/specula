"use client";

import { useState } from "react";
import { Chip } from "@/components/atoms/chip";
import { Toggle } from "@/components/atoms/toggle";
import { setCompanyTracking, type CompanyRow } from "@/lib/api/companies";

export function CompaniesView({ companies }: { companies: CompanyRow[] }) {
  const [q, setQ] = useState("");
  const [tracking, setTracking] = useState<Record<string, boolean>>({});
  const query = q.toLowerCase();
  const rows = companies.filter(
    (c) =>
      c.name.toLowerCase().includes(query) ||
      c.hq.toLowerCase().includes(query),
  );
  const totalOpen = companies.reduce((s, c) => s + c.open, 0);

  return (
    <section
      data-screen-label="companies"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            Companies
          </h1>
          <p className="max-w-[64ch] text-[13.5px] text-ink-2">
            Approved companies in the registry — ATS provider and feed, enriched
            HQ country with confidence, and a rough comp estimate (informational
            only). Global across every lens.
          </p>
        </div>
        <div className="flex items-center gap-[14px] font-mono text-[11.5px] text-ink-2">
          <div>
            <b className="text-[15px] font-semibold text-ink">
              {companies.length}
            </b>{" "}
            tracked
          </div>
          <span className="h-[26px] w-px bg-rule" />
          <div>
            <b className="text-[15px] font-semibold text-ink">{totalOpen}</b>{" "}
            open roles
          </div>
        </div>
      </header>

      <div className="mt-[16px] mb-[6px] flex items-center justify-between font-mono text-[11px] text-ink-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter by name or HQ country…"
          className="w-full max-w-[280px] rounded-[9px] border border-rule-2 bg-card px-[12px] py-[8px] font-body text-[13.5px] text-ink focus:border-ink focus:outline-none"
        />
        <span>
          {rows.length} of {companies.length}
        </span>
      </div>

      <table className="mt-[18px] w-full border-collapse">
        <thead>
          <tr>
            {[
              "Company",
              "ATS feed",
              "HQ country",
              "HQ confidence",
              "Open",
              "Comp est.",
              "Tracking",
            ].map((h) => (
              <th
                key={h}
                className="border-b border-rule px-[14px] pb-[11px] text-left font-mono text-[9.5px] font-normal uppercase tracking-[0.08em] text-ink-3"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => {
            const low = c.conf < 80;
            const rowKey = c.id ?? c.name;
            const on = tracking[rowKey] ?? c.tracking ?? true;
            const toggle = (next: boolean) => {
              setTracking((t) => ({ ...t, [rowKey]: next }));
              if (c.id) {
                setCompanyTracking(c.id, next).catch(() =>
                  setTracking((t) => ({ ...t, [rowKey]: !next })),
                );
              }
            };
            return (
              <tr key={c.name} className="transition-colors hover:bg-panel">
                <td className="border-b border-rule px-[14px] py-[15px] align-middle text-[13.5px]">
                  <div className="flex items-center gap-[11px] font-semibold">
                    <div className="flex h-[30px] w-[30px] items-center justify-center rounded-[7px] bg-panel-2 font-mono text-[10px] font-semibold text-ink-2">
                      {c.logo}
                    </div>
                    <div>
                      <div>{c.name}</div>
                      <div className="mt-px font-mono text-[11px] font-normal text-ink-2">
                        {c.domain}
                      </div>
                    </div>
                  </div>
                </td>
                <td className="border-b border-rule px-[14px] py-[15px] align-middle text-[13.5px]">
                  <span className="rounded-[5px] bg-panel-2 px-[8px] py-[3px] font-mono text-[11px] text-ink">
                    {c.ats}
                  </span>
                </td>
                <td className="border-b border-rule px-[14px] py-[15px] align-middle text-[13.5px]">
                  {c.flag} {c.hq}
                </td>
                <td className="border-b border-rule px-[14px] py-[15px] align-middle text-[13.5px]">
                  <span
                    className={`inline-flex items-center gap-[8px] font-mono text-[11.5px] ${low ? "text-warn" : ""}`}
                  >
                    <span className="h-[5px] w-[46px] overflow-hidden rounded-[3px] bg-panel-2">
                      <span
                        className={`block h-full ${low ? "bg-warn" : "bg-accent"}`}
                        style={{ width: `${c.conf}%` }}
                      />
                    </span>
                    {c.conf}%{low ? " ⚐" : ""}
                  </span>
                </td>
                <td className="border-b border-rule px-[14px] py-[15px] align-middle font-mono text-[13.5px]">
                  {c.open}
                </td>
                <td className="border-b border-rule px-[14px] py-[15px] align-middle text-[13.5px]">
                  <Chip strong>{c.comp}</Chip>
                </td>
                <td className="border-b border-rule px-[14px] py-[15px] align-middle text-[13.5px]">
                  <Toggle on={on} onChange={toggle} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
