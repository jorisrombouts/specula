import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { IntroGate } from "@/components/intro/intro-gate";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
beforeEach(() => sessionStorage.clear());

describe("IntroGate", () => {
  it("renders the intro once per session (absent when the flag is set)", () => {
    render(<IntroGate roles={13} isNew={7} />);
    // first mount, flag unset → overlay shows
    expect(screen.getByText("Specula")).toBeInTheDocument();
    // simulate a later mount in the same session with the flag set
    sessionStorage.setItem("specula_intro", "1");
    cleanup();
    render(<IntroGate roles={13} isNew={7} />);
    expect(screen.queryByText("Specula")).toBeNull();
  });

  it("shows the DERIVED counts (13 roles / 7 new)", () => {
    // Drive the useCountUp animation to completion synchronously, same
    // technique as src/lib/use-count-up.test.ts.
    let now = 0;
    vi.spyOn(globalThis, "requestAnimationFrame").mockImplementation(
      (cb: FrameRequestCallback) => {
        now += 1600;
        cb(now);
        return 0;
      },
    );
    vi.spyOn(globalThis, "cancelAnimationFrame").mockImplementation(() => {});
    render(<IntroGate roles={13} isNew={7} />);
    expect(screen.getByText(/roles tracked/)).toHaveTextContent("13");
    expect(screen.getByText(/roles tracked/)).toHaveTextContent("7");
  });
});
