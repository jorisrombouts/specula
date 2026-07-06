import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  act,
  waitFor,
} from "@testing-library/react";
import { TweaksProvider, useTweaks } from "@/lib/tweaks";
import { STORAGE_KEY, TWEAK_DEFAULTS } from "@/lib/tweaks-init";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
beforeEach(() => localStorage.clear());

function Probe() {
  const { tweaks, setTweak } = useTweaks();
  return (
    <div>
      <span data-testid="mstyle">{tweaks.mstyle}</span>
      <button onClick={() => setTweak("mstyle", "ring")}>ring</button>
    </div>
  );
}

describe("TweaksProvider", () => {
  it("defaults when localStorage is empty", () => {
    render(
      <TweaksProvider>
        <Probe />
      </TweaksProvider>,
    );
    expect(screen.getByTestId("mstyle")).toHaveTextContent("bars");
  });

  it("reads a persisted tweak on mount", async () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ mstyle: "figure" }));
    render(
      <TweaksProvider>
        <Probe />
      </TweaksProvider>,
    );
    // reconciled by the mount effect
    expect(await screen.findByText("figure")).toBeInTheDocument();
  });

  it("setTweak updates state and persists to localStorage", () => {
    render(
      <TweaksProvider>
        <Probe />
      </TweaksProvider>,
    );
    act(() => {
      fireEvent.click(screen.getByText("ring"));
    });
    expect(screen.getByTestId("mstyle")).toHaveTextContent("ring");
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!).mstyle).toBe("ring");
  });

  it("reconciles from the server on mount (server is source of truth)", async () => {
    const server = { ...TWEAK_DEFAULTS, mstyle: "figure" };
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: true, json: async () => server })),
    );

    render(
      <TweaksProvider>
        <Probe />
      </TweaksProvider>,
    );

    expect(await screen.findByText("figure")).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith("/api/tweaks");
    // the server value is also written back to the localStorage cache
    await waitFor(() =>
      expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!).mstyle).toBe(
        "figure",
      ),
    );
  });

  it("a user edit wins over a slow initial server GET", async () => {
    // GET resolves only after the user has already edited; its (stale) value
    // must not clobber the edit.
    let resolveGet: (v: unknown) => void = () => {};
    const server = { ...TWEAK_DEFAULTS, mstyle: "figure" };
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) => {
        if (init?.method === "PUT") {
          return Promise.resolve({
            ok: true,
            json: async () => JSON.parse(init.body as string),
          });
        }
        return new Promise((resolve) => {
          resolveGet = resolve;
        });
      }),
    );

    render(
      <TweaksProvider>
        <Probe />
      </TweaksProvider>,
    );

    act(() => {
      fireEvent.click(screen.getByText("ring"));
    });
    expect(screen.getByTestId("mstyle")).toHaveTextContent("ring");

    // Now the in-flight GET resolves with the pre-edit value.
    await act(async () => {
      resolveGet({ ok: true, json: async () => server });
    });

    expect(screen.getByTestId("mstyle")).toHaveTextContent("ring");
  });

  it("setTweak PUTs the new tweaks to the server", async () => {
    const fetchMock = vi.fn((_url: string, init?: RequestInit) =>
      Promise.resolve({
        ok: true,
        json: async () =>
          init?.method === "PUT"
            ? JSON.parse(init.body as string)
            : TWEAK_DEFAULTS,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <TweaksProvider>
        <Probe />
      </TweaksProvider>,
    );
    act(() => {
      fireEvent.click(screen.getByText("ring"));
    });

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/tweaks",
        expect.objectContaining({ method: "PUT" }),
      ),
    );
    const putCall = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "PUT",
    )!;
    expect(JSON.parse((putCall[1] as RequestInit).body as string).mstyle).toBe(
      "ring",
    );
  });
});
