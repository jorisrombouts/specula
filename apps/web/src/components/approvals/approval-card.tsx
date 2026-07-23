import type { Approval } from "@specula/shared-types";
import type { ApprovalDecision } from "@/lib/api/approvals";
import { Chip } from "@/components/atoms/chip";
import { Tag } from "@/components/atoms/tag";
import { Button } from "@/components/atoms/button";
import { CompanyLogo } from "@/components/atoms/company-logo";

export function ApprovalCard({
  approval: c,
  onDecide,
}: {
  approval: Approval;
  onDecide?: (decision: ApprovalDecision) => void;
}) {
  return (
    <div
      data-appr={c.id}
      className="flex flex-col gap-[13px] rounded-[14px] border border-rule bg-card p-[18px_20px] shadow-card"
    >
      <div className="flex items-start gap-[12px]">
        <CompanyLogo
          src={c.logo}
          name={c.name}
          className="flex h-[40px] w-[40px] shrink-0 items-center justify-center rounded-[9px] bg-panel-2 font-mono text-[13px] font-semibold text-ink"
        />
        <div className="flex-1">
          <div className="text-[15px] font-semibold">
            {c.name} <span className="text-[13px]">{c.flag}</span>
          </div>
          <div className="mt-[2px] font-mono text-[11px] text-ink-2">
            {c.domain}
          </div>
        </div>
        <Chip mono>{c.roles} open</Chip>
      </div>
      <p className="text-[12.5px] leading-[1.5] text-ink-2">{c.why}</p>
      <div className="flex flex-wrap gap-[7px]">
        <span className="rounded-[5px] bg-panel-2 px-[8px] py-[3px] font-mono text-[11px] text-ink">
          {c.ats}
        </span>
        {c.unverified ? (
          <Tag variant="flag">⚐ HQ origin unverified</Tag>
        ) : (
          <Chip mono>HQ {c.hq}</Chip>
        )}
      </div>
      <div className="flex items-center gap-[6px] font-mono text-[10.5px] text-ink-3">
        ⌕ found via &quot;{c.query}&quot;
      </div>
      <div className="mt-[2px] flex gap-[8px]">
        <Button
          variant="accent"
          className="flex-1 justify-center"
          onClick={() => onDecide?.("approve")}
        >
          ✓ Approve
        </Button>
        <Button
          className="flex-1 justify-center"
          onClick={() => onDecide?.("reject")}
        >
          ✕ Reject
        </Button>
        <Button title="Snooze" onClick={() => onDecide?.("snooze")}>
          ☾
        </Button>
      </div>
    </div>
  );
}
