"use client";

import { useState } from "react";
import { Chip } from "@/components/atoms/chip";
import { CompanyLogo } from "@/components/atoms/company-logo";
import { optOutCompany, type CompanyRow } from "@/lib/api/companies";

export function CompaniesView({ companies }: { companies: CompanyRow[] }) {
  const [q, setQ] = useState("");
  const [removed, setRemoved] = useState<Set<string>>(new Set());
  const query = q.toLowerCase();
  const remaining = companies.filter((c) => !removed.has(c.id ?? c.name));
  const rows = remaining.filter(
    (c) =>
      c.name.toLowerCase().includes(query) ||
      c.hq.toLowerCase().includes(query),
  );
  const totalOpen = remaining.reduce((s, c) => s + c.open, 0);

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
              {remaining.length}
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
          {rows.length} of {remaining.length}
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
              "",
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
            const remove = () => {
              setRemoved((prev) => new Set(prev).add(rowKey));
              if (c.id) {
                optOutCompany(c.id).catch(() =>
                  setRemoved((prev) => {
                    const next = new Set(prev);
                    next.delete(rowKey);
                    return next;
                  }),
                );
              }
            };
            return (
              <tr key={c.name} className="transition-colors hover:bg-panel">
                <td className="border-b border-rule px-[14px] py-[15px] align-middle text-[13.5px]">
                  <div className="flex items-center gap-[11px] font-semibold">
                    <CompanyLogo
                      src={c.logo}
                      name={c.name}
                      className="flex h-[30px] w-[30px] items-center justify-center rounded-[7px] bg-panel-2 font-mono text-[10px] font-semibold text-ink-2"
                    />
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
                  <button
                    type="button"
                    onClick={remove}
                    className="font-mono text-[11px] text-ink-3 transition-colors hover:text-warn"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
