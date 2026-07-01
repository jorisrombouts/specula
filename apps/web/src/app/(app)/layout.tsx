import { Sidebar } from "@/components/sidebar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid h-screen grid-cols-[236px_1fr] overflow-hidden">
      <Sidebar />
      <main className="main-scroll relative overflow-y-auto">{children}</main>
    </div>
  );
}
