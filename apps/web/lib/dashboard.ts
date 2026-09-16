import { apiRequest } from "./api";
import { getAuthToken } from "./auth";

export type DashboardData = {
  user: {
    email: string;
  };
  resume: {
    status: "ready" | "not_ready";
    name: string | null;
  };
  ats: {
    score: number | null;
    status: "pass" | "needs_improvement" | "not_checked" | "not_available";
  };
  jobs: {
    available: boolean;
  };
  applications: {
    available: boolean;
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