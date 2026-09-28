import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

let token: string | null = "token-123";

vi.mock("./auth", () => ({
  getAuthToken: () => token,
  authHeaders: () => (token ? { Authorization: `Bearer ${token}` } : {}),
}));

import { ApiError } from "./api";
import { getPreferences, updatePreferences, type Preferences } from "./preferences";

const preferences: Preferences = {
  employment_types: ["full_time"],
  locations: ["Austin, TX"],
  remote_preference: "remote",
  target_titles: ["Data Engineer"],
  excluded_locations: [],
  requires_sponsorship: false,
  is_us_citizen: null,
  has_security_clearance: null,
  enforce_minimum_experience: true,
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function lastCall(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls.at(-1) as unknown as [string, RequestInit];
}

beforeEach(() => {
  token = "token-123";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("preferences API client", () => {
  it("reads /preferences/me with GET and the bearer token", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(preferences));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getPreferences()).resolves.toEqual(preferences);

    const [url, init] = lastCall(fetchMock);
    expect(url).toMatch(/\/preferences\/me$/);
    expect(init.method).toBeUndefined();
    expect(init.body).toBeUndefined();
    expect(init.headers).toEqual({
      "Content-Type": "application/json",
      Authorization: "Bearer token-123",
    });
  });

  it("returns null when nothing has been saved yet", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(null)));

    await expect(getPreferences()).resolves.toBeNull();
  });

  it("sends no Authorization header when signed out", async () => {
    token = null;
    const fetchMock = vi.fn(async () => jsonResponse(null));
    vi.stubGlobal("fetch", fetchMock);

    await getPreferences();

    expect(lastCall(fetchMock)[1].headers).not.toHaveProperty(
      "Authorization",
    );
  });

  it("saves with PUT, a JSON body and an explicit Content-Type", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(preferences));
    vi.stubGlobal("fetch", fetchMock);

    await expect(updatePreferences(preferences)).resolves.toEqual(preferences);

    const [url, init] = lastCall(fetchMock);
    expect(url).toMatch(/\/preferences\/me$/);
    expect(init.method).toBe("PUT");
    expect(init.body).toBe(JSON.stringify(preferences));
    expect(init.headers).toEqual({
      "Content-Type": "application/json",
      Authorization: "Bearer token-123",
    });
  });

  it("rejects with the backend's error message and status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "Invalid value." }, 422)),
    );

    const error: unknown = await updatePreferences(preferences).catch(
      (err: unknown) => err,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ message: "Invalid value.", status: 422 });
  });
});
