import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

let token: string | null = "token-123";

vi.mock("./auth", () => ({
  getAuthToken: () => token,
  authHeaders: () => (token ? { Authorization: `Bearer ${token}` } : {}),
}));

import { ApiError } from "./api";
import {
  authenticatedRequest,
  fetchResumeVersionFile,
  getResumes,
  getResumeVersions,
} from "./resumes";

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

describe("resume API client", () => {
  it("lists resumes with GET and the bearer token", async () => {
    const fetchMock = vi.fn(async () => jsonResponse([{ id: "r1" }]));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getResumes()).resolves.toEqual([{ id: "r1" }]);

    const [url, init] = lastCall(fetchMock);
    expect(url).toMatch(/\/resumes$/);
    expect(init.method).toBeUndefined();
    expect(init.headers).toMatchObject({
      Authorization: "Bearer token-123",
    });
  });

  it("lists a resume's versions", async () => {
    const fetchMock = vi.fn(async () => jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await getResumeVersions("r1");

    expect(lastCall(fetchMock)[0]).toMatch(/\/resumes\/r1\/versions$/);
  });

  it("sends no Authorization header when signed out", async () => {
    token = null;
    const fetchMock = vi.fn(async () => jsonResponse([]));
    vi.stubGlobal("fetch", fetchMock);

    await getResumes();

    expect(lastCall(fetchMock)[1].headers).not.toHaveProperty(
      "Authorization",
    );
  });
});

describe("authenticatedRequest", () => {
  it("adds the bearer token and lets caller headers win", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ id: "u1" }));
    vi.stubGlobal("fetch", fetchMock);

    await authenticatedRequest("/resumes/upload", {
      method: "POST",
      headers: { Authorization: "Bearer caller", "X-Extra": "1" },
    });

    const [url, init] = lastCall(fetchMock);
    expect(url).toMatch(/\/resumes\/upload$/);
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({
      Authorization: "Bearer caller",
      "X-Extra": "1",
    });
  });

  it("adds no abort signal when no timeoutMs is given", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);

    await authenticatedRequest("/resumes/versions/v1/ai-analysis");

    expect(lastCall(fetchMock)[1].signal).toBeUndefined();
  });

  it("passes timeoutMs through, so a hung request rejects with the timeout error", async () => {
    const hungFetch = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new DOMException("The operation was aborted.", "AbortError"));
          });
        }),
    );
    vi.stubGlobal("fetch", hungFetch);

    await expect(
      authenticatedRequest(
        "/resumes/versions/v1/ai-analysis",
        { method: "POST" },
        50,
      ),
    ).rejects.toMatchObject({
      message: "The request took too long to respond. Please try again.",
      status: 0,
    });
  });

  it("rejects with the backend's error message and status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "Not found." }, 404)),
    );

    const error: unknown = await authenticatedRequest(
      "/resumes/versions/v1/ai-analysis",
    ).catch((err: unknown) => err);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ message: "Not found.", status: 404 });
  });
});

describe("fetchResumeVersionFile", () => {
  it("returns the file as a Blob, sending the bearer token", async () => {
    const fetchMock = vi.fn(
      async () => new Response("%PDF-1.4", { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const blob = await fetchResumeVersionFile("v1");

    expect(await blob.text()).toBe("%PDF-1.4");
    const [url, init] = lastCall(fetchMock);
    expect(url).toMatch(/\/resumes\/versions\/v1\/file$/);
    expect(init.headers).toEqual({ Authorization: "Bearer token-123" });
  });

  it("sends no headers when signed out", async () => {
    token = null;
    const fetchMock = vi.fn(async () => new Response("x", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await fetchResumeVersionFile("v1");

    expect(lastCall(fetchMock)[1].headers).toEqual({});
  });

  it("throws an ApiError with the response status on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "Forbidden" }, 403)),
    );

    const error: unknown = await fetchResumeVersionFile("v1").catch(
      (err: unknown) => err,
    );

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      message: "Unable to retrieve the resume file.",
      status: 403,
    });
  });
});
