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

export type JobIntelligenceSkill = {
  canonical_skill: string;
  level: "required" | "preferred";
  evidence_text: string;
  confidence: "high" | "medium" | "low";
};

export type JobIntelligenceExperience = {
  level: "required" | "preferred";
  minimum_years: number | null;
  maximum_years: number | null;
  area: string | null;
  context: string | null;
  evidence_text: string;
  confidence: "high" | "medium" | "low";
};

export type JobIntelligenceEducation = {
  level: "required" | "preferred";
  degree_level: string | null;
  field_of_study: string | null;
  evidence_text: string;
  confidence: "high" | "medium" | "low";
};

export type JobIntelligenceCertification = {
  level: "required" | "preferred";
  name: string;
  evidence_text: string;
  confidence: "high" | "medium" | "low";
};

export type JobIntelligenceResponsibility = {
  description: string;
  evidence_text: string;
};

export type JobIntelligenceData = {
  identity: {
    original_title: string;
    normalized_title: string | null;
    role_family: string | null;
    seniority: string | null;
  };
  employment: {
    employment_type: string;
    evidence_text: string | null;
  };
  location: {
    raw_location: string | null;
    city: string | null;
    state: string | null;
    country: string | null;
    additional_locations: string[];
    remote_type: string;
    work_arrangement_text: string | null;
    relocation_mentioned: boolean;
  };
  required_skills: JobIntelligenceSkill[];
  preferred_skills: JobIntelligenceSkill[];
  required_experience: JobIntelligenceExperience[];
  preferred_experience: JobIntelligenceExperience[];
  education: JobIntelligenceEducation[];
  certifications: JobIntelligenceCertification[];
  responsibilities: JobIntelligenceResponsibility[];
  authorization: {
    sponsorship: string;
    citizenship: string;
    clearance: string;
    work_authorization: string;
  };
  compensation: {
    salary_min: number | null;
    salary_max: number | null;
    currency: string | null;
    period: string;
    evidence_text: string | null;
  };
  domain: {
    value: string | null;
    confidence: string | null;
  };
};

export type JobIntelligenceResponse = {
  id: string;
  job_id: string;
  analysis_version: string;
  extraction_status: string;
  created_at: string;
  intelligence: JobIntelligenceData;
};

export type EligibilityStatus = "eligible" | "ineligible" | "unknown";

export type EligibilityCheckStatus = "pass" | "fail" | "unknown" | "not_applicable";

export type EligibilityCheck = {
  constraint: string;
  status: EligibilityCheckStatus;
  reason: string;
};

export type JobEligibilityResult = {
  id: string;
  job_id: string;
  status: EligibilityStatus;
  engine_version: string;
  checks: EligibilityCheck[];
  failed_constraints: string[];
  unknown_constraints: string[];
  reasons: string[];
  evaluated_at: string;
};

function authHeaders(): Record<string, string> {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("ai_job_intelligence_token")
      : null;

  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function getJobIntelligence(
  jobId: string,
): Promise<JobIntelligenceResponse> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/intelligence`, {
    headers: authHeaders(),
    cache: "no-store",
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : "Unable to load Job Intelligence.";

    throw new Error(message);
  }

  return data as JobIntelligenceResponse;
}

export async function generateJobIntelligence(
  jobId: string,
): Promise<JobIntelligenceResponse> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/intelligence`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    cache: "no-store",
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : "Unable to generate Job Intelligence.";

    throw new Error(message);
  }

  return data as JobIntelligenceResponse;
}

export async function getJobEligibility(
  jobId: string,
): Promise<JobEligibilityResult> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/eligibility`, {
    headers: authHeaders(),
    cache: "no-store",
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : "Unable to check eligibility.";

    throw new Error(message);
  }

  return data as JobEligibilityResult;
}

export type AtsAlignmentStatus = "matched" | "partial" | "missing";

export type AtsRequirementCategory = "must_have" | "preferred";

export type AtsRequirementResult = {
  requirement_id: string;
  requirement_type: "skill" | "experience" | "education" | "certification";
  category: AtsRequirementCategory;
  requirement_text: string;
  status: AtsAlignmentStatus;
  jd_evidence: string;
  resume_evidence: string | null;
  explanation: string;
  confidence: "high" | "medium" | "low";
};

export type AtsAlignmentResult = {
  id: string;
  job_id: string;
  resume_version_id: string;
  job_intelligence_id: string;
  engine_version: string;
  overall_score: number;
  confidence: "high" | "medium" | "low";
  scoring_version: string;
  must_have_total: number;
  must_have_matched: number;
  preferred_total: number;
  preferred_matched: number;
  requirement_results: AtsRequirementResult[];
  created_at: string;
};

export async function calculateAtsAlignment(
  jobId: string,
): Promise<AtsAlignmentResult> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/ats`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    cache: "no-store",
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      typeof data?.detail === "string"
        ? data.detail
        : "Unable to calculate ATS Alignment.";

    throw new Error(message);
  }

  return data as AtsAlignmentResult;
}

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