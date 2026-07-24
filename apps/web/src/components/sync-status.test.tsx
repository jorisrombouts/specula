import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import type { Run } from "@specula/shared-types";

let hookReturn: {
  run: Run | null;
  triggering: boolean;
  error: string | null;
  trigger: () => Promise<void>;
};
vi.mock("@/lib/use-latest-run", () => ({ useLatestRun: () => hookReturn }));

const { SyncStatus } = await import("@/components/sync-status");

afterEach(cleanup);

beforeEach(() => {
  hookReturn = {
    run: null,
    triggering: false,
    error: null,
    trigger: vi.fn(async () => {}),
  };
});

describe("SyncStatus", () => {
  it("shows the trigger error as an alert", () => {
    hookReturn = { ...hookReturn, error: "Rate-limited — try again in 42s." };
    render(<SyncStatus initialRun={null} />);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Rate-limited — try again in 42s.",
    );
  });

  it("shows no alert when there is no error", () => {
    render(<SyncStatus initialRun={null} />);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
