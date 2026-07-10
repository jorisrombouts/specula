import { redirect } from "next/navigation";
import { getSession } from "@/auth";
import { Sidebar } from "@/components/sidebar";
import { IntroGate } from "@/components/intro/intro-gate";
import { getJobsPool } from "@/lib/api/jobs";
import { getLatestRun } from "@/lib/api/runs";
import { TweaksProvider } from "@/lib/tweaks";
import { TweaksPanel } from "@/components/tweaks/tweaks-panel";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();
  // Local-only auth bypass for verification — double-gated so it can NEVER
  // activate in production (NODE_ENV is "production" on Vercel).
  const bypass =
    process.env.NODE_ENV !== "production" &&
    process.env.DEV_AUTH_BYPASS === "1";
  const user =
    session?.user ??
    (bypass ? { name: "Dev (bypass)", email: "dev@local" } : null);
  if (!user) redirect("/signin");
  const pool = await getJobsPool();
  const roles = pool.length;
  const isNew = pool.filter((j) => j.isNew).length;
  const latestRun = await getLatestRun();
  return (
    <TweaksProvider>
      <div className="grid h-screen grid-cols-[236px_1fr] overflow-hidden">
        <IntroGate roles={roles} isNew={isNew} />
        <Sidebar user={user} latestRun={latestRun} />
        <main className="main-scroll relative overflow-y-auto">{children}</main>
      </div>
      <TweaksPanel />
    </TweaksProvider>
  );
}
