import { apiRequest } from "./api";

export type User = {
  id: string;
  email: string;
};

type LoginResponse = {
  access_token: string;
  token_type: string;
};

const TOKEN_KEY = "ai_job_intelligence_token";

export async function register(
  email: string,
  password: string,
): Promise<User> {
  return apiRequest<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
    }),
  });
}

export async function login(
  email: string,
  password: string,
): Promise<User> {
  const token = await apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
    }),
  });

  if (typeof window !== "undefined") {
    localStorage.setItem(TOKEN_KEY, token.access_token);
  }

  return getCurrentUser();
}

export async function getCurrentUser(): Promise<User> {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem(TOKEN_KEY)
      : null;

  if (!token) {
    throw new Error("Not authenticated");
  }

  return apiRequest<User>("/auth/me", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

export function logout(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function getAuthToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  return localStorage.getItem(TOKEN_KEY);
}

// AJI-035 — the one shared "silent, optional auth" header builder: no
// token means an empty header object (the request proceeds unauthenticated
// rather than failing), matching the behavior every one of its callers
// already had independently. This does NOT cover the small number of
// call sites (lib/applications.ts, lib/dashboard.ts, lib/job-discovery.ts)
// that deliberately throw "Not authenticated" instead - that is a
// different, intentional contract and stays as its own local code.
export function authHeaders(): Record<string, string> {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

type MessageResponse = {
  message: string;
};

export async function forgotPassword(
  email: string,
): Promise<MessageResponse> {
  return apiRequest<MessageResponse>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({
      email,
    }),
  });
}

export async function resetPassword(
  token: string,
  newPassword: string,
): Promise<MessageResponse> {
  return apiRequest<MessageResponse>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({
      token,
      new_password: newPassword,
    }),
  });
}