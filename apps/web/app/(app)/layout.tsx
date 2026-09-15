import Sidebar from "./dashboard/components/sidebar";
import DashboardHeader from "./dashboard/components/dashboard-header";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[#05070A] text-[#F2F5F8]">
      <Sidebar />

      <div className="min-h-screen md:pl-64">
        <DashboardHeader />

        <main className="min-h-[calc(100vh-...]">
          {children}
        </main>
      </div>
    </div>
  );
}