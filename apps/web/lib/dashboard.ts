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
    // The most recent ATS Alignment result across any job — there is no
    // resume-level ATS score, only a per-(user, job, resume) one.
    score: number | null;
    checked_at: string | null;
  };
  jobs: {
    // Real count of active jobs first discovered today.
    today_count: number;
    // Employment types actually present among today's real jobs — never a
    // static list of every type the system supports.
    today_employment_types: string[];
  };
  applications: {
    // Application tracking has no backend model yet; always false.
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