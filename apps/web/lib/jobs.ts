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