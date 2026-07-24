"use client";

import { useState } from "react";
import type { Approval } from "@specula/shared-types";
import { ApprovalCard } from "@/components/approvals/approval-card";
import {
  postApprovalDecision,
  type ApprovalDecision,
} from "@/lib/api/approvals";

export function ApprovalsView({ approvals }: { approvals: Approval[] }) {
  const [queue, setQueue] = useState(approvals);
  const [approved, setApproved] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Optimistically drop the card; the "N approved" header stays DERIVED from
  // decisions made. Roll back AND surface why if the decision fails to persist.
  async function decide(approval: Approval, decision: ApprovalDecision) {
    setError(null);
    setQueue((q) => q.filter((a) => a.id !== approval.id));
    if (decision === "approve") setApproved((n) => n + 1);
    try {
      await postApprovalDecision(approval.id, decision);
    } catch (e) {
      setQueue((q) => [approval, ...q]);
      if (decision === "approve") setApproved((n) => n - 1);
      setError(e instanceof Error ? e.message : "Action failed.");
    }
  }

  return (
    <section
      data-screen-label="approvals"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            Approval queue
          </h1>
          <p className="max-w-[64ch] text-[13.5px] text-ink-2">
            Discovery surfaces candidate companies against your targeting.
            Approve once — on approval each is enriched (HQ country +
            confidence, rough comp) and added to the registry. Rejections
            suppress repeats.
          </p>
        </div>
        <div className="flex items-center gap-[14px] font-mono text-[11.5px] text-ink-2">
          <div>
            <b className="text-[15px] font-semibold text-ink">{queue.length}</b>{" "}
            pending
          </div>
          <span className="h-[26px] w-px bg-rule" />
          <div>
            <b className="text-[15px] font-semibold text-ink">{approved}</b>{" "}
            approved
          </div>
        </div>
      </header>

      {error ? (
        <div role="alert" className="mt-[16px] font-mono text-[12px] text-warn">
          {error}
        </div>
      ) : null}

      {queue.length === 0 ? (
        <div className="px-[20px] py-[80px] text-center text-ink-2">
          <div className="mb-[14px] text-[34px] opacity-40">✓</div>
          Queue clear. Next discovery run is scheduled for Monday.
        </div>
      ) : (
        <div className="mt-[20px] grid grid-cols-2 gap-[14px]">
          {queue.map((c) => (
            <ApprovalCard
              key={c.id}
              approval={c}
              onDecide={(decision) => decide(c, decision)}
            />
          ))}
        </div>
      )}
    </section>
  );
}
