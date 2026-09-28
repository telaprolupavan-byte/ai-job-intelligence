// @vitest-environment jsdom
//
// AJI-035 — regression harness for lib/jobs.ts's request implementations,
// written against the pre-migration behavior so it locks in exact current
// semantics (error types, timeouts, headers, 404 handling) before the fetch
// clients are consolidated. These tests exercise the real fetch path via a
// stubbed global fetch, never `vi.mock("./jobs")`. jsdom (not the default
// node environment) plus the real localStorage-backed token is used
// instead of mocking "./auth", so the assertions hold unchanged whether the
// token is read inline (pre-migration) or via the shared auth helper
// (post-migration) - both ultimately read the same storage key.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./api";
import {
  calculateAtsAlignment,
  calculateGapAnalysis,
  calculateJobMatch,
  createResumeImprovement,
  generateJobIntelligence,
  getGapAnalysis,
  getJob,
  getJobEligibility,
  getJobIntelligence,
  getJobs,
  getLatestJobResults,
  getResumeImprovement,
  ResumeImprovementError,
  runResumeImprovementRecheck,
  submitJob,
} from "./jobs";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function lastCall(fetchMock: ReturnType<typeof vi.fn>) {
  return fetchMock.mock.calls.at(-1) as unknown as [string, RequestInit];
}

function hungFetch() {
  return vi.fn(
    (_url: string, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          reject(new DOMException("The operation was aborted.", "AbortError"));
        });
      }),
  );
}

const TOKEN_KEY = "ai_job_intelligence_token";

function signIn() {
  localStorage.setItem(TOKEN_KEY, "token-123");
}

function signOut() {
  localStorage.removeItem(TOKEN_KEY);
}

beforeEach(() => {
  signIn();
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("getJobs", () => {
  it("issues a GET with query params, cache: no-store, and the bearer token", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({ jobs: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await getJobs({ search: "engineer", page: 2 });

    const [url, init] = lastCall(fetchMock);
    expect(url).toMatch(/\/jobs\?/);
    expect(url).toMatch(/search=engineer/);
    expect(url).toMatch(/page=2/);
    expect(init.headers).toMatchObject({ Authorization: "Bearer token-123" });
    expect(init.cache).toBe("no-store");
  });

  it("sends no Authorization header when signed out", async () => {
    signOut();
    const fetchMock = vi.fn(async () =>
      jsonResponse({ jobs: [], pagination: { page: 1, page_size: 20, total: 0, total_pages: 0 } }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await getJobs({});

    expect(lastCall(fetchMock)[1].headers).not.toHaveProperty("Authorization");
  });

  it("rejects with ApiError once its 20-second timeout elapses on a hung request", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", hungFetch());

    const pending = getJobs({});
    const assertion = expect(pending).rejects.toMatchObject({
      message: "The request took too long to respond. Please try again.",
      status: 0,
    });

    await vi.advanceTimersByTimeAsync(20_000);
    await assertion;
  });

  it("throws ApiError carrying the HTTP status on a non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "Invalid criteria." }, 422)),
    );

    const error: unknown = await getJobs({}).catch((err: unknown) => err);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ message: "Invalid criteria.", status: 422 });
  });
});

describe("submitJob", () => {
  it("POSTs the trimmed content and rejects with ApiError once its 300-second timeout elapses", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", hungFetch());

    const pending = submitJob({ content: "a job posting" });
    const assertion = expect(pending).rejects.toMatchObject({
      message: "The request took too long to respond. Please try again.",
      status: 0,
    });

    await vi.advanceTimersByTimeAsync(300_000);
    await assertion;
  });

  it("does not time out before 300 seconds", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", hungFetch());

    const pending = submitJob({ content: "x" });
    const settled = { done: false };
    pending.catch(() => {
      settled.done = true;
    });

    await vi.advanceTimersByTimeAsync(299_000);
    expect(settled.done).toBe(false);

    await vi.advanceTimersByTimeAsync(1_000);
    await pending.catch(() => undefined);
    expect(settled.done).toBe(true);
  });
});

describe("getJob", () => {
  it("resolves the job and adds no abort signal when no timeout is used", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ id: "j1" }));
    vi.stubGlobal("fetch", fetchMock);

    await getJob("j1");

    expect(lastCall(fetchMock)[1].signal).toBeUndefined();
  });

  it("throws ApiError with status on failure", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: "Not found." }, 404)));

    const error: unknown = await getJob("missing").catch((err: unknown) => err);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ message: "Not found.", status: 404 });
  });
});

describe("getLatestJobResults", () => {
  it("resolves each artifact to null on its own 404, without affecting the others", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("/match")) return jsonResponse({ id: "m1" });
      return jsonResponse({ detail: "Not found." }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getLatestJobResults("j1", "v1");

    expect(result.match).toEqual({ id: "m1" });
    expect(result.ats).toBeNull();
    expect(result.gapAnalysis).toBeNull();
    expect(result.improvement).toBeNull();
  });

  it("rethrows a non-404 failure instead of coalescing it to null", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: "Server error." }, 500)));

    await expect(getLatestJobResults("j1", "v1")).rejects.toMatchObject({
      message: "Server error.",
      status: 500,
    });
  });
});

describe("jobs.ts raw-fetch functions (Job Intelligence / Eligibility / ATS / Match / Gap Analysis)", () => {
  it("getJobIntelligence: parses JSON, sends the bearer token, and adds no abort signal (no timeout)", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ id: "ji1" }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await getJobIntelligence("j1");

    expect(result).toEqual({ id: "ji1" });
    const [url, init] = lastCall(fetchMock);
    expect(url).toMatch(/\/jobs\/j1\/intelligence$/);
    expect(init.headers).toMatchObject({ Authorization: "Bearer token-123" });
    expect(init.signal).toBeUndefined();
  });

  it("getJobIntelligence: throws a plain Error (no status) with the string detail on failure", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: "JD not analyzable." }, 422)));

    const error: unknown = await getJobIntelligence("j1").catch((err: unknown) => err);
    expect(error).toBeInstanceOf(Error);
    expect(error).not.toBeInstanceOf(ApiError);
    expect((error as Error).message).toBe("JD not analyzable.");
    expect((error as ApiError).status).toBeUndefined();
  });

  it("getJobIntelligence: falls back to its own generic message when detail is not a string", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({}, 500)));

    const error: unknown = await getJobIntelligence("j1").catch((err: unknown) => err);
    expect((error as Error).message).toBe("Unable to load Job Intelligence.");
  });

  it("generateJobIntelligence: POSTs with Content-Type and the bearer token", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ id: "ji2" }));
    vi.stubGlobal("fetch", fetchMock);

    await generateJobIntelligence("j1");

    const [, init] = lastCall(fetchMock);
    expect(init.method).toBe("POST");
    expect(init.headers).toMatchObject({
      "Content-Type": "application/json",
      Authorization: "Bearer token-123",
    });
  });

  it("getJobEligibility: sends no Authorization header when signed out", async () => {
    signOut();
    const fetchMock = vi.fn(async () => jsonResponse({ status: "eligible" }));
    vi.stubGlobal("fetch", fetchMock);

    await getJobEligibility("j1");

    expect(lastCall(fetchMock)[1].headers).toEqual({});
  });

  it("calculateAtsAlignment: appends resume_version_id only when provided", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ id: "a1" }));
    vi.stubGlobal("fetch", fetchMock);

    await calculateAtsAlignment("j1");
    expect(lastCall(fetchMock)[0]).toMatch(/\/jobs\/j1\/ats$/);

    await calculateAtsAlignment("j1", "v9");
    expect(lastCall(fetchMock)[0]).toMatch(/\/jobs\/j1\/ats\?resume_version_id=v9$/);
  });

  it("calculateJobMatch: attaches the bearer token and has no timeout", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ id: "m1" }));
    vi.stubGlobal("fetch", fetchMock);

    await calculateJobMatch("j1", "v1");

    const [url, init] = lastCall(fetchMock);
    expect(url).toMatch(/\/jobs\/j1\/match\?resume_version_id=v1$/);
    expect(init.headers).toMatchObject({ Authorization: "Bearer token-123" });
    expect(init.signal).toBeUndefined();
  });

  it("calculateJobMatch: sends no Authorization header when signed out", async () => {
    signOut();
    const fetchMock = vi.fn(async () => jsonResponse({ id: "m1" }));
    vi.stubGlobal("fetch", fetchMock);

    await calculateJobMatch("j1");

    expect(lastCall(fetchMock)[1].headers).not.toHaveProperty("Authorization");
  });

  it("getGapAnalysis / calculateGapAnalysis: GET and POST, own fallback message on failure", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({}, 503)));

    const getError: unknown = await getGapAnalysis("j1").catch((err: unknown) => err);
    expect((getError as Error).message).toBe("Unable to load Gap Analysis.");

    const postError: unknown = await calculateGapAnalysis("j1").catch((err: unknown) => err);
    expect((postError as Error).message).toBe("Unable to calculate Gap Analysis.");
  });
});

describe("Resume Improvement ({code, message} error payloads)", () => {
  it("getResumeImprovement: maps { detail: { code, message } } to ResumeImprovementError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({ detail: { code: "truth_confirmation_required", message: "Confirm it." } }, 422),
      ),
    );

    const error: unknown = await getResumeImprovement("j1").catch((err: unknown) => err);
    expect(error).toBeInstanceOf(ResumeImprovementError);
    expect((error as ResumeImprovementError).code).toBe("truth_confirmation_required");
    expect((error as ResumeImprovementError).message).toBe("Confirm it.");
  });

  it("createResumeImprovement: maps a plain string detail to ResumeImprovementError with code 'error'", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: "Bad request." }, 400)));

    const error: unknown = await createResumeImprovement("j1", "ga1", []).catch((err: unknown) => err);
    expect(error).toBeInstanceOf(ResumeImprovementError);
    expect((error as ResumeImprovementError).code).toBe("error");
    expect((error as ResumeImprovementError).message).toBe("Bad request.");
  });

  it("createResumeImprovement: sends the decisions body as JSON", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ id: "ri1" }));
    vi.stubGlobal("fetch", fetchMock);

    await createResumeImprovement("j1", "ga1", [
      { requirement_id: "r1", action: "approve", truth_confirmed: true },
    ]);

    const [, init] = lastCall(fetchMock);
    expect(JSON.parse(init.body as string)).toEqual({
      gap_analysis_id: "ga1",
      decisions: [{ requirement_id: "r1", action: "approve", truth_confirmed: true }],
    });
  });

  it("runResumeImprovementRecheck: falls back to its own generic message with no detail", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({}, 500)));

    const error: unknown = await runResumeImprovementRecheck("j1", "ri1").catch(
      (err: unknown) => err,
    );
    expect(error).toBeInstanceOf(ResumeImprovementError);
    expect((error as ResumeImprovementError).message).toBe("Unable to recheck your new version.");
  });
});
