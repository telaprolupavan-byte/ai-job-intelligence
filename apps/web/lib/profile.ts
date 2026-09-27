import { apiRequest } from "./api";
import { getAuthToken } from "./auth";

export type Profile = {
  full_name: string | null;
  phone: string | null;
  location: string | null;
  summary: string | null;
  years_experience: number | null;
  target_titles: string[] | null;
};

function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// null when the user has not saved a profile yet.
export function getProfile(): Promise<Profile | null> {
  return apiRequest<Profile | null>("/profile/me", {
    headers: authHeaders(),
  });
}

export function updateProfile(profile: Profile): Promise<Profile> {
  return apiRequest<Profile>("/profile/me", {
    method: "PUT",
    headers: {
      ...authHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(profile),
  });
}
