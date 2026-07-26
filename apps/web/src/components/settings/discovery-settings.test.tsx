import { describe, it, expect, vi, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { DiscoverySettings } from "@/components/settings/discovery-settings";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("DiscoverySettings", () => {
  it("renders the current cap and a cost hint", () => {
    render(<DiscoverySettings initial={10} />);
    expect(screen.getByLabelText("discovery searches per run")).toHaveValue(
      "10",
    );
    expect(screen.getByText("10 searches")).toBeInTheDocument();
    expect(screen.getByText(/≈ \$0\.20 · ~70s per run/)).toBeInTheDocument();
  });

  it("Save is disabled until the value changes", () => {
    render(<DiscoverySettings initial={10} />);
    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText("discovery searches per run"), {
      target: { value: "5" },
    });
    expect(save).toBeEnabled();
    expect(screen.getByText("5 searches")).toBeInTheDocument();
  });

  it("PUTs /api/settings/discovery with the chosen value on Save", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));
    render(<DiscoverySettings initial={10} />);
    fireEvent.change(screen.getByLabelText("discovery searches per run"), {
      target: { value: "7" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/settings/discovery");
    expect(init?.method).toBe("PUT");
    expect(JSON.parse(init?.body as string)).toEqual({ maxSearches: 7 });
    await waitFor(() => expect(screen.getByText("Saved.")).toBeInTheDocument());
  });

  it("surfaces an error when the save fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 500 }),
    );
    render(<DiscoverySettings initial={10} />);
    fireEvent.change(screen.getByLabelText("discovery searches per run"), {
      target: { value: "3" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/Failed to save/),
    );
  });
});
