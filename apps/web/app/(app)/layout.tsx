import Sidebar from "./dashboard/components/sidebar";
import DashboardHeader from "./dashboard/components/dashboard-header";
import AuthGate from "./auth-gate";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGate>
      <div className="min-h-screen bg-app-bg text-app-text">
        <Sidebar />

        <div className="lg:pl-[220px]">
          <DashboardHeader />

          <main>{children}</main>
        </div>
      </div>
    </AuthGate>
  );
}
