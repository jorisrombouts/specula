import { GoogleSignInButton } from "@/components/google-sign-in-button";

export default function SignInPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-paper">
      <div className="flex flex-col items-center gap-1">
        <span className="font-display text-[34px] font-semibold tracking-[0.02em] text-ink">
          Specula
        </span>
        <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-3">
          role ledger
        </span>
      </div>
      <GoogleSignInButton />
    </main>
  );
}
