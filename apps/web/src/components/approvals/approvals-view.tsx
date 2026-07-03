import type { Approval } from "@specula/shared-types";
import { ApprovalCard } from "@/components/approvals/approval-card";

export function ApprovalsView({ approvals }: { approvals: Approval[] }) {
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
            <b className="text-[15px] font-semibold text-ink">
              {approvals.length}
            </b>{" "}
            pending
          </div>
          <span className="h-[26px] w-px bg-rule" />
          <div>
            <b className="text-[15px] font-semibold text-ink">0</b> approved
          </div>
        </div>
      </header>

      {approvals.length === 0 ? (
        <div className="px-[20px] py-[80px] text-center text-ink-2">
          <div className="mb-[14px] text-[34px] opacity-40">✓</div>
          Queue clear. Next discovery run is scheduled for Monday.
        </div>
      ) : (
        <div className="mt-[20px] grid grid-cols-2 gap-[14px]">
          {approvals.map((c) => (
            <ApprovalCard key={c.id} approval={c} />
          ))}
        </div>
      )}
    </section>
  );
}
