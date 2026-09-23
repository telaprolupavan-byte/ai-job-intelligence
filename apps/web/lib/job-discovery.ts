import { apiRequest } from "./api";
import { getAuthToken } from "./auth";

/**
 * AJI-024 — user-safe Job Discovery state for the Jobs UI
 * (GET /job-discovery/status). Carries no configuration values, provider
 * credentials, or run error text; running discovery stays an internal,
 * shared-secret operation that users can never trigger.
 */
export type DiscoveryStatus = {
  source_configured: boolean;
  /** The synthetic test-fixture provider is enabled (dev/test only). */
  test_mode: boolean;
  last_run: {
    status: "running" | "succeeded" | "failed" | string;
    completed_at: string | null;
  } | null;
};

export async function getDiscoveryStatus(): Promise<DiscoveryStatus> {
  const token = getAuthToken();

  if (!token) {
    throw new Error("Not authenticated");
  }

  return apiRequest<DiscoveryStatus>(
    "/job-discovery/status",
    {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    },
    10_000,
  );
}
