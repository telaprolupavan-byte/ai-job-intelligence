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

        <div className="min-h-screen lg:pl-64">
          <DashboardHeader />

          <main className="min-h-screen">{children}</main>
        </div>
      </div>
    </AuthGate>
  );
}
