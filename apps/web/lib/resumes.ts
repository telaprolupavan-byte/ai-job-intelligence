import { apiRequest } from "./api";
import { getAuthToken } from "./auth";

export type Resume = {
  id: string;
  filename: string;
  created_at: string;
  has_text: boolean;
  version_count: number;
  master_version_id: string | null;
  master_version_name: string | null;
  master_version_created_at: string | null;
};

export type ResumeVersion = {
  id: string;
  resume_id: string;
  name: string;
  original_filename: string;
  content_text: string;
  is_master: boolean;
  has_analysis: boolean;
  created_at: string;

  // AJI-021 lineage. `parent_version_id` is null for an uploaded
  // version; `source` is "upload", "improvement" (AJI-021) or
  // "general_improvement" (AJI-027); `has_file` is false for a generated
  // version, which has no document to download.
  parent_version_id: string | null;
  source: "upload" | "improvement" | "general_improvement";
  has_file: boolean;
};

function authenticatedRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getAuthToken();

  return apiRequest<T>(path, {
    ...options,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });
}

export function getResumes(): Promise<Resume[]> {
  return authenticatedRequest<Resume[]>("/resumes");
}

export function getResumeVersions(
  resumeId: string,
): Promise<ResumeVersion[]> {
  return authenticatedRequest<ResumeVersion[]>(
    `/resumes/${resumeId}/versions`,
  );
}
