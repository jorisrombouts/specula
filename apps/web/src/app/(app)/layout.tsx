import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { Sidebar } from "@/components/sidebar";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  // Local-only auth bypass for verification — double-gated so it can NEVER
  // activate in production (NODE_ENV is "production" on Vercel).
  const bypass =
    process.env.NODE_ENV !== "production" &&
    process.env.DEV_AUTH_BYPASS === "1";
  const user =
    session?.user ??
    (bypass ? { name: "Dev (bypass)", email: "dev@local" } : null);
  if (!user) redirect("/signin");
  return (
    <div className="grid h-screen grid-cols-[236px_1fr] overflow-hidden">
      <Sidebar user={user} />
      <main className="main-scroll relative overflow-y-auto">{children}</main>
    </div>
  );
}
