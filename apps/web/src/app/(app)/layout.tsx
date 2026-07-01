import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { Sidebar } from "@/components/sidebar";

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session?.user) redirect("/signin");
  return (
    <div className="grid h-screen grid-cols-[236px_1fr] overflow-hidden">
      <Sidebar user={session.user} />
      <main className="main-scroll relative overflow-y-auto">{children}</main>
    </div>
  );
}
