import { describe, it, expect, afterEach, beforeEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  act,
} from "@testing-library/react";
import { TweaksProvider, useTweaks } from "@/lib/tweaks";
import { STORAGE_KEY } from "@/lib/tweaks-init";

afterEach(cleanup);
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
});
