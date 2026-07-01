import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";

const signIn = vi.fn();
vi.mock("next-auth/react", () => ({ signIn }));

afterEach(() => {
  cleanup();
  signIn.mockClear();
});

describe("GoogleSignInButton", () => {
  it("renders a 'Sign in with Google' button", async () => {
    const { GoogleSignInButton } =
      await import("@/components/google-sign-in-button");
    render(<GoogleSignInButton />);
    expect(
      screen.getByRole("button", { name: /sign in with google/i }),
    ).toBeInTheDocument();
  });

  it("calls signIn('google') on click", async () => {
    const { GoogleSignInButton } =
      await import("@/components/google-sign-in-button");
    render(<GoogleSignInButton />);
    fireEvent.click(
      screen.getByRole("button", { name: /sign in with google/i }),
    );
    expect(signIn).toHaveBeenCalledWith("google", { redirectTo: "/jobs" });
  });
});
