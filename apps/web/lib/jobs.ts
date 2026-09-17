export type Job = {
  id: string;
  title: string;
  company: string | null;
  location: string | null;
  country: string;
  remote_type: string | null;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  contract_duration: string | null;
  contract_worker_type: string | null;
  description: string | null;
  requirements: string | null;
  responsibilities: string | null;
  posting_date: string | null;
  source: string;
  source_url: string | null;
  application_url: string | null;
  first_seen_at: string;
  last_seen_at: string;
};

export type JobsResponse = {
  jobs: Job[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function getJobs(params: {
  search?: string;
  employment_type?: string;
  remote_type?: string;
  location?: string;
  page?: number;
  page_size?: number;
} = {}): Promise<JobsResponse> {
  const searchParams = new URLSearchParams();

  if (params.search) {
    searchParams.set("search", params.search);
  }

  if (params.employment_type) {
    searchParams.set("employment_type", params.employment_type);
  }

  if (params.remote_type) {
    searchParams.set("remote_type", params.remote_type);
  }

  if (params.location) {
    searchParams.set("location", params.location);
  }

  searchParams.set("page", String(params.page ?? 1));
  searchParams.set("page_size", String(params.page_size ?? 20));

  const response = await fetch(
    `${API_BASE_URL}/jobs?${searchParams.toString()}`,
    {
      cache: "no-store",
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch jobs: ${response.status}`);
  }

  return response.json();
}
export type SkillEvidence = {
  skill: string;
  status: "matched" | "missing" | "uncertain";
  evidence_type:
    | "explicit"
    | "experience"
    | "project"
    | "education"
    | "inferred"
    | "none";
  evidence: string | null;
};

export type MatchComponent = {
  name: string;
  score: number;
  max_score: number;
  explanation: string;
};

export type JobMatchResult = {
  id: string;
  job_id: string;
  resume_version_id: string;
  score: number;
  confidence: string;
  engine_version: string;
  strengths: string[];
  skill_gaps: string[];
  components: MatchComponent[];
  must_have_matches: SkillEvidence[];
  must_have_gaps: SkillEvidence[];
  preferred_matches: SkillEvidence[];
  preferred_gaps: SkillEvidence[];
};

export async function calculateJobMatch(
  jobId: string,
): Promise<JobMatchResult> {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("ai_job_intelligence_token")
      : null;

  const response = await fetch(
    `${API_BASE_URL}/jobs/${jobId}/match`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token
          ? {
              Authorization: `Bearer ${token}`,
            }
          : {}),
      },
      cache: "no-store",
    },
  );

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : "Unable to calculate job match.";

    throw new Error(message);
  }

  return data as JobMatchResult;
}