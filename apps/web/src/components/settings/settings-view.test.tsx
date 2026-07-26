import { describe, it, expect, vi, afterEach } from "vitest";
import {
  render,
  screen,
  cleanup,
  fireEvent,
  waitFor,
} from "@testing-library/react";

const deleteAccount = vi.fn();
const signOut = vi.fn();
vi.mock("@/lib/api/account", () => ({ deleteAccount }));
vi.mock("next-auth/react", () => ({ signOut }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

async function renderView() {
  const { SettingsView } = await import("@/components/settings/settings-view");
  render(<SettingsView initialMaxSearches={10} />);
}

describe("SettingsView", () => {
  it("offers a download link to the export route", async () => {
    await renderView();
    const link = screen.getByRole("link", { name: /export my data/i });
    expect(link).toHaveAttribute("href", "/api/account/export");
    expect(link).toHaveAttribute("download", "specula-export.json");
  });

  it("does not delete without an explicit confirm step", async () => {
    await renderView();
    fireEvent.click(screen.getByRole("button", { name: /delete my account/i }));
    // Now in the confirm state — the destructive action has NOT fired yet.
    expect(deleteAccount).not.toHaveBeenCalled();
    expect(
      screen.getByText(/are you sure\? this is permanent/i),
    ).toBeInTheDocument();
  });

  it("deletes then signs out when confirmed", async () => {
    deleteAccount.mockResolvedValue(undefined);
    signOut.mockResolvedValue(undefined);
    await renderView();

    fireEvent.click(screen.getByRole("button", { name: /delete my account/i }));
    fireEvent.click(
      screen.getByRole("button", { name: /yes, delete everything/i }),
    );

    await waitFor(() => expect(deleteAccount).toHaveBeenCalledTimes(1));
    expect(signOut).toHaveBeenCalledWith({ redirectTo: "/signin" });
  });

  it("cancelling the confirm returns to the idle state", async () => {
    await renderView();
    fireEvent.click(screen.getByRole("button", { name: /delete my account/i }));
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(deleteAccount).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: /delete my account/i }),
    ).toBeInTheDocument();
  });

  it("surfaces an error and does not sign out when deletion fails", async () => {
    deleteAccount.mockRejectedValue(new Error("boom"));
    await renderView();

    fireEvent.click(screen.getByRole("button", { name: /delete my account/i }));
    fireEvent.click(
      screen.getByRole("button", { name: /yes, delete everything/i }),
    );

    await waitFor(() =>
      expect(
        screen.getByText(/something went wrong deleting your account/i),
      ).toBeInTheDocument(),
    );
    expect(signOut).not.toHaveBeenCalled();
  });
});
