"use client";

import { signIn } from "next-auth/react";

export function GoogleSignInButton() {
  return (
    <button
      type="button"
      onClick={() => signIn("google", { redirectTo: "/jobs" })}
      className="font-body rounded-[7px] border border-rule-2 bg-card px-4 py-[9px] text-[13px] font-medium text-ink transition-colors hover:border-ink"
    >
      Sign in with Google
    </button>
  );
}
