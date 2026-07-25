import { describe, it, expect, afterEach, vi } from "vitest";
import {
  render,
  screen,
  within,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { ApprovalsView } from "@/components/approvals/approvals-view";
import { ApprovalCard } from "@/components/approvals/approval-card";

vi.mock("@/lib/api/bff", async () => {
  const { mockBffFetch } = await import("@/lib/api/test-fixtures");
  return { bffFetch: mockBffFetch };
});
vi.mock("@/lib/api/approvals", async (importActual) => {
  const actual = await importActual<typeof import("@/lib/api/approvals")>();
  return {
    ...actual,
    postApprovalDecision: vi.fn().mockResolvedValue(undefined),
  };
});
// The header's "Find new companies" button uses useRouter (via useLatestRun).
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const { getApprovals, postApprovalDecision } =
  await import("@/lib/api/approvals");

afterEach(() => {
  cleanup();
  vi.mocked(postApprovalDecision).mockClear();
});

const approvals = await getApprovals();
const verified = approvals.find((a) => !a.unverified)!;
const unverified = approvals.find((a) => a.unverified)!;

describe("ApprovalsView", () => {
  it("renders the DERIVED pending count and 0 approved", () => {
    const { container } = render(
      <ApprovalsView approvals={approvals} latestRun={null} />,
    );
    const header = container.querySelector("header")!;
    expect(header).toHaveTextContent("6");
    expect(header).toHaveTextContent("pending");
    expect(header).toHaveTextContent("0");
    expect(header).toHaveTextContent("approved");
  });

  it("renders one card per approval", () => {
    const { container } = render(
      <ApprovalsView approvals={approvals} latestRun={null} />,
    );
    expect(container.querySelectorAll("[data-appr]")).toHaveLength(6);
  });

  it("approving posts the decision, drops the card, and increments approved", async () => {
    const { container } = render(
      <ApprovalsView approvals={approvals} latestRun={null} />,
    );
    const header = container.querySelector("header")!;
    const card = container.querySelector(`[data-appr="${verified.id}"]`)!;

    fireEvent.click(within(card as HTMLElement).getByText("✓ Approve"));

    await waitFor(() => {
      expect(
        container.querySelector(`[data-appr="${verified.id}"]`),
      ).toBeNull();
    });
    expect(postApprovalDecision).toHaveBeenCalledWith(verified.id, "approve");
    expect(within(header).getByText("5")).toBeInTheDocument(); // pending
    expect(within(header).getByText("1")).toBeInTheDocument(); // approved
  });

  it("rejecting drops the card without incrementing approved", async () => {
    const { container } = render(
      <ApprovalsView approvals={approvals} latestRun={null} />,
    );
    const header = container.querySelector("header")!;
    const card = container.querySelector(`[data-appr="${verified.id}"]`)!;

    fireEvent.click(within(card as HTMLElement).getByText("✕ Reject"));

    await waitFor(() => {
      expect(
        container.querySelector(`[data-appr="${verified.id}"]`),
      ).toBeNull();
    });
    expect(postApprovalDecision).toHaveBeenCalledWith(verified.id, "reject");
    expect(within(header).getByText("5")).toBeInTheDocument(); // pending
    expect(within(header).getByText("0")).toBeInTheDocument(); // approved unchanged
  });

  it("snoozing drops the card without incrementing approved", async () => {
    const { container } = render(
      <ApprovalsView approvals={approvals} latestRun={null} />,
    );
    const card = container.querySelector(`[data-appr="${verified.id}"]`)!;

    fireEvent.click(within(card as HTMLElement).getByTitle("Snooze"));

    await waitFor(() => {
      expect(
        container.querySelector(`[data-appr="${verified.id}"]`),
      ).toBeNull();
    });
    expect(postApprovalDecision).toHaveBeenCalledWith(verified.id, "snooze");
  });

  it("renders the 'Find new companies' discovery button in the header", () => {
    const { container } = render(
      <ApprovalsView approvals={approvals} latestRun={null} />,
    );
    const header = container.querySelector("header")!;
    expect(
      within(header).getByRole("button", { name: "Find new companies" }),
    ).toBeInTheDocument();
  });

  it("merges newly-discovered approvals into the queue when props refresh", () => {
    const { container, rerender } = render(
      <ApprovalsView approvals={approvals} latestRun={null} />,
    );
    expect(container.querySelectorAll("[data-appr]")).toHaveLength(6);

    // A completed discovery run → router.refresh() → the page re-renders with a
    // longer approvals list. The freshly-found company must appear in the queue.
    const discovered = { ...approvals[0], id: "newly-found-1" };
    rerender(
      <ApprovalsView approvals={[discovered, ...approvals]} latestRun={null} />,
    );
    expect(container.querySelectorAll("[data-appr]")).toHaveLength(7);
    expect(
      container.querySelector('[data-appr="newly-found-1"]'),
    ).not.toBeNull();
  });

  it("restores the card and shows the reason when a decision fails", async () => {
    vi.mocked(postApprovalDecision).mockRejectedValueOnce(
      new Error("Rate-limited — try again in 30s."),
    );
    const { container } = render(
      <ApprovalsView approvals={approvals} latestRun={null} />,
    );
    const card = container.querySelector(`[data-appr="${verified.id}"]`)!;

    fireEvent.click(within(card as HTMLElement).getByText("✓ Approve"));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Rate-limited — try again in 30s.",
      ),
    );
    // rolled back — the card is still in the queue
    expect(
      container.querySelector(`[data-appr="${verified.id}"]`),
    ).not.toBeNull();
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

  it("links the domain to the careers page in a new tab", () => {
    render(<ApprovalCard approval={verified} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", verified.careersUrl!);
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("hides the description paragraph when the company blurb is blank", () => {
    const { container } = render(
      <ApprovalCard approval={{ ...verified, why: "" }} />,
    );
    expect(container.querySelector("p")).toBeNull();
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

  it("renders the three action buttons", () => {
    render(<ApprovalCard approval={verified} />);
    expect(screen.getByText("✓ Approve")).toBeInTheDocument();
    expect(screen.getByText("✕ Reject")).toBeInTheDocument();
    expect(screen.getByTitle("Snooze")).toBeInTheDocument();
  });
});
