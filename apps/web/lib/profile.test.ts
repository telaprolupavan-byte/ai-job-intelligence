import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

let token: string | null = "token-123";

vi.mock("./auth", () => ({
  getAuthToken: () => token,
}));

import { ApiError } from "./api";
import { getProfile, updateProfile, type Profile } from "./profile";

const profile: Profile = {
  full_name: "Ada Lovelace",
  phone: null,
  location: "Austin, TX",
  summary: null,
  years_experience: 5,
  target_titles: ["Data Engineer"],
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

describe("profile API client", () => {
  it("reads /profile/me with GET and the bearer token", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(profile));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getProfile()).resolves.toEqual(profile);

    const [url, init] = lastCall(fetchMock);
    expect(url).toMatch(/\/profile\/me$/);
    expect(init.method).toBeUndefined();
    expect(init.body).toBeUndefined();
    expect(init.headers).toEqual({
      "Content-Type": "application/json",
      Authorization: "Bearer token-123",
    });
  });

  it("returns null when nothing has been saved yet", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(null)));

    await expect(getProfile()).resolves.toBeNull();
  });

  it("sends no Authorization header when signed out", async () => {
    token = null;
    const fetchMock = vi.fn(async () => jsonResponse(null));
    vi.stubGlobal("fetch", fetchMock);

    await getProfile();

    expect(lastCall(fetchMock)[1].headers).not.toHaveProperty(
      "Authorization",
    );
  });

  it("saves with PUT, a JSON body and an explicit Content-Type", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(profile));
    vi.stubGlobal("fetch", fetchMock);

    await expect(updateProfile(profile)).resolves.toEqual(profile);

    const [url, init] = lastCall(fetchMock);
    expect(url).toMatch(/\/profile\/me$/);
    expect(init.method).toBe("PUT");
    expect(init.body).toBe(JSON.stringify(profile));
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

    const error: unknown = await updateProfile(profile).catch(
      (err: unknown) => err,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ message: "Invalid value.", status: 422 });
  });
});
