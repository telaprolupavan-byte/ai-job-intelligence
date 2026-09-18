import { apiRequest } from "./api";
import { getAuthToken } from "./auth";

export type DashboardJobPreview = {
  id: string;
  title: string;
  company: string | null;
  location: string | null;
  employment_type: string | null;
  remote_type: string | null;
};

export type DashboardData = {
  user: {
    email: string;
  };
  resume: {
    status: "ready" | "not_ready";
    name: string | null;
  };
  validation: {
    status: "pending" | "analyzed";
  };
  ats: {
    score: number | null;
    status: "pass" | "needs_improvement" | "not_checked" | "not_available";
  };
  last_checked_at: string | null;
  jobs: {
    available: boolean;
    today_count: number;
    full_time_count: number;
    contract_count: number;
    recent: DashboardJobPreview[];
  };
  applications: {
    available: boolean;
    active_count: number;
  };
};

export async function getDashboard(): Promise<DashboardData> {
  const token = getAuthToken();

  if (!token) {
    throw new Error("Not authenticated");
  }

  return apiRequest<DashboardData>("/dashboard", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}
