"use client";

import { useState } from "react";
import { signOut } from "next-auth/react";
import { deleteAccount } from "@/lib/api/account";

type DeleteState = "idle" | "confirming" | "deleting" | "error";

export function SettingsView() {
  const [state, setState] = useState<DeleteState>("idle");

  async function confirmDelete() {
    setState("deleting");
    try {
      await deleteAccount();
      // Data is gone; clear the stateless session too so the deleted account can't be
      // re-bootstrapped by the auth dependency on the next request.
      await signOut({ redirectTo: "/signin" });
    } catch {
      setState("error");
    }
  }

  return (
    <section
      data-screen-label="settings"
      className="mx-auto max-w-[1180px] px-[34px] pt-[30px] pb-16"
    >
      <header className="mb-1 flex items-end justify-between border-b-[1.5px] border-ink pb-[18px]">
        <div className="flex flex-col gap-[7px]">
          <h1 className="m-0 font-display text-[34px] font-semibold leading-none tracking-[-0.01em]">
            Settings
          </h1>
          <p className="max-w-[64ch] text-[13.5px] text-ink-2">
            Your data, on your terms. Export everything Specula holds about you,
            or delete your account entirely.
          </p>
        </div>
      </header>

      <div className="mt-[24px] flex max-w-[760px] flex-col gap-[20px]">
        <div className="rounded-[11px] border border-rule-2 bg-card p-[20px]">
          <h2 className="m-0 font-display text-[18px] font-semibold tracking-[-0.01em]">
            Export your data
          </h2>
          <p className="mt-[6px] mb-[14px] max-w-[60ch] text-[13px] text-ink-2">
            Download a complete JSON copy of your profile, targeting, tracked
            companies, postings, scores, search profiles, runs, and LLM-cost
            ledger. Global reference data is not personal to you and is
            excluded.
          </p>
          <a
            href="/api/account/export"
            download="specula-export.json"
            className="inline-flex items-center rounded-[7px] border border-rule-2 bg-panel px-4 py-[9px] text-[13px] font-medium text-ink transition-colors hover:border-ink"
          >
            Export my data
          </a>
        </div>

        <div className="rounded-[11px] border border-warn bg-warn-bg p-[20px]">
          <h2 className="m-0 font-display text-[18px] font-semibold tracking-[-0.01em] text-warn">
            Delete account
          </h2>
          <p className="mt-[6px] mb-[14px] max-w-[60ch] text-[13px] text-ink-2">
            Permanently delete your account and everything tied to it —
            companies, postings, scores, runs, and cost history. This cannot be
            undone.
          </p>

          {state === "idle" || state === "error" ? (
            <button
              type="button"
              onClick={() => setState("confirming")}
              className="inline-flex items-center rounded-[7px] border border-warn bg-card px-4 py-[9px] text-[13px] font-medium text-warn transition-colors hover:bg-warn hover:text-paper"
            >
              Delete my account
            </button>
          ) : (
            <div className="flex flex-wrap items-center gap-[12px]">
              <span className="text-[13px] font-medium text-warn">
                Are you sure? This is permanent.
              </span>
              <button
                type="button"
                onClick={confirmDelete}
                disabled={state === "deleting"}
                className="inline-flex items-center rounded-[7px] border border-warn bg-warn px-4 py-[9px] text-[13px] font-medium text-paper transition-opacity hover:opacity-90 disabled:opacity-60"
              >
                {state === "deleting" ? "Deleting…" : "Yes, delete everything"}
              </button>
              <button
                type="button"
                onClick={() => setState("idle")}
                disabled={state === "deleting"}
                className="inline-flex items-center rounded-[7px] border border-rule-2 bg-card px-4 py-[9px] text-[13px] font-medium text-ink transition-colors hover:border-ink disabled:opacity-60"
              >
                Cancel
              </button>
            </div>
          )}

          {state === "error" ? (
            <p className="mt-[12px] text-[12.5px] text-warn">
              Something went wrong deleting your account. Please try again.
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
