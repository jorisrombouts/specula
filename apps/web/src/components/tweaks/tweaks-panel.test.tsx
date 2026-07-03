import { describe, it, expect, afterEach, beforeEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  cleanup,
  within,
} from "@testing-library/react";
import { TweaksProvider } from "@/lib/tweaks";
import { TweaksPanel } from "@/components/tweaks/tweaks-panel";
import { STORAGE_KEY } from "@/lib/tweaks-init";

afterEach(cleanup);
beforeEach(() => localStorage.clear());

function mount() {
  return render(
    <TweaksProvider>
      <TweaksPanel />
    </TweaksProvider>,
  );
}

describe("TweaksPanel", () => {
  it("opens on the toggle button and shows the 5 controls", () => {
    mount();
    // panel hidden until toggled
    expect(screen.queryByText("Match score")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /tweaks/i }));
    for (const label of [
      "Match score",
      "Job layout",
      "Display font",
      "Accent",
      "Spacing",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("switching Job layout to cards persists layout=cards", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: /tweaks/i }));
    // the Job-layout segmented control has a 'cards' option
    fireEvent.click(screen.getByRole("radio", { name: "cards" }));
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!).layout).toBe("cards");
  });

  it("closes on the ✕", () => {
    mount();
    fireEvent.click(screen.getByRole("button", { name: /tweaks/i }));
    fireEvent.click(screen.getByLabelText("Close tweaks"));
    expect(screen.queryByText("Match score")).toBeNull();
  });
});
