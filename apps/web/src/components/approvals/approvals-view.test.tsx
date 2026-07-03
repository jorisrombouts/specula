import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ApprovalsView } from "@/components/approvals/approvals-view";
import { ApprovalCard } from "@/components/approvals/approval-card";
import { getApprovals } from "@/lib/api/approvals";

afterEach(cleanup);
const approvals = getApprovals();
const verified = approvals.find((a) => !a.unverified)!;
const unverified = approvals.find((a) => a.unverified)!;

describe("ApprovalsView", () => {
  it("renders the DERIVED pending count and 0 approved (inert)", () => {
    const { container } = render(<ApprovalsView approvals={approvals} />);
    const header = container.querySelector("header")!;
    expect(header).toHaveTextContent("6");
    expect(header).toHaveTextContent("pending");
    expect(header).toHaveTextContent("0");
    expect(header).toHaveTextContent("approved");
  });

  it("renders one card per approval", () => {
    const { container } = render(<ApprovalsView approvals={approvals} />);
    expect(container.querySelectorAll("[data-appr]")).toHaveLength(6);
  });
});

describe("ApprovalCard", () => {
  it("renders name, domain, why, roles chip, ATS, and query", () => {
    render(<ApprovalCard approval={verified} />);
    expect(screen.getByText(verified.name)).toBeInTheDocument();
    expect(screen.getByText(verified.domain)).toBeInTheDocument();
    expect(screen.getByText(verified.why)).toBeInTheDocument();
    expect(screen.getByText(`${verified.roles} open`)).toBeInTheDocument();
    expect(screen.getByText(verified.ats)).toBeInTheDocument();
    expect(
      screen.getByText(`⌕ found via "${verified.query}"`),
    ).toBeInTheDocument();
  });

  it("shows the HQ chip for a verified approval", () => {
    render(<ApprovalCard approval={verified} />);
    expect(screen.getByText(`HQ ${verified.hq}`)).toBeInTheDocument();
    expect(screen.queryByText(/origin unverified/)).toBeNull();
  });

  it("shows the unverified flag instead of the HQ chip when unverified", () => {
    render(<ApprovalCard approval={unverified} />);
    expect(screen.getByText("⚐ HQ origin unverified")).toBeInTheDocument();
    expect(screen.queryByText(`HQ ${unverified.hq}`)).toBeNull();
  });

  it("renders the three action buttons (inert — no handlers)", () => {
    render(<ApprovalCard approval={verified} />);
    expect(screen.getByText("✓ Approve")).toBeInTheDocument();
    expect(screen.getByText("✕ Reject")).toBeInTheDocument();
    expect(screen.getByText("☾")).toBeInTheDocument();
  });
});
