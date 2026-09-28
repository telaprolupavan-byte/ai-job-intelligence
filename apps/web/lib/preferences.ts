import { apiRequest } from "./api";
import { authHeaders } from "./auth";

export type Preferences = {
  employment_types: string[] | null;
  locations: string[] | null;
  remote_preference: string | null;
  target_titles: string[] | null;
  // Hard eligibility fields (AJI-011). Unlike the soft preferences
  // above, these can make a job INELIGIBLE outright, independent of any
  // Job Match score. Leaving one unset never excludes a job.
  excluded_locations: string[] | null;
  requires_sponsorship: boolean | null;
  is_us_citizen: boolean | null;
  has_security_clearance: boolean | null;
  enforce_minimum_experience: boolean;
};

// null when the user has not saved preferences yet.
export function getPreferences(): Promise<Preferences | null> {
  return apiRequest<Preferences | null>("/preferences/me", {
    headers: authHeaders(),
  });
}

export function updatePreferences(
  preferences: Preferences,
): Promise<Preferences> {
  return apiRequest<Preferences>("/preferences/me", {
    method: "PUT",
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(preferences),
  });
}
