import { apiRequest } from "./api";
import { getAuthToken } from "./auth";

export type ApplicationStatus =
  | "saved"
  | "applied"
  | "interviewing"
  | "offer"
  | "rejected"
  | "withdrawn";

export const APPLICATION_STATUSES: ApplicationStatus[] = [
  "saved",
  "applied",
  "interviewing",
  "offer",
  "rejected",
  "withdrawn",
];

export type ApplicationJobSummary = {
  id: string;
  title: string;
  company: string | null;
  location: string | null;
  employment_type: string | null;
  remote_type: string | null;
  application_url: string | null;
};

export type Application = {
  id: string;
  job: ApplicationJobSummary;
  status: ApplicationStatus;
  applied_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ApplicationStatusEvent = {
  status: ApplicationStatus;
  created_at: string;
};

export type ApplicationDetail = Application & {
  status_history: ApplicationStatusEvent[];
};

function authHeaders(): Record<string, string> {
  const token = getAuthToken();

  if (!token) {
    throw new Error("Not authenticated");
  }

  return { Authorization: `Bearer ${token}` };
}

export async function saveJob(jobId: string): Promise<Application> {
  return apiRequest<Application>("/applications", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ job_id: jobId }),
  });
}

export async function getApplications(): Promise<Application[]> {
  return apiRequest<Application[]>("/applications", {
    headers: authHeaders(),
  });
}

export async function getApplicationDetail(
  applicationId: string,
): Promise<ApplicationDetail> {
  return apiRequest<ApplicationDetail>(`/applications/${applicationId}`, {
    headers: authHeaders(),
  });
}

export async function updateApplicationStatus(
  applicationId: string,
  status: ApplicationStatus,
): Promise<Application> {
  return apiRequest<Application>(`/applications/${applicationId}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify({ status }),
  });
}

export async function removeSavedJob(applicationId: string): Promise<void> {
  await apiRequest<null>(`/applications/${applicationId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
}
