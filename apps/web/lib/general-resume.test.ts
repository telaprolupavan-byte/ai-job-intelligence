import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createGeneralAssessment,
  GeneralResumeError,
  getGeneralAssessment,
  retryGeneralRecheck,
  submitGeneralReview,
} from "./general-resume";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("general resume API client", () => {
  it("reads the saved assessment with GET and no job parameter", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ id: "a" }));
    vi.stubGlobal("fetch", fetchMock);

    await getGeneralAssessment("v1");

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/resumes\/versions\/v1\/general-assessment$/);
    expect(init.method).toBeUndefined();
    expect(url).not.toMatch(/job/);
  });

  it("returns null when the version has not been assessed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({ detail: { code: "assessment_not_found", message: "x" } }, 404),
      ),
    );

    await expect(getGeneralAssessment("v1")).resolves.toBeNull();
  });

  it("still throws a 404 for a version that is not found", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({ detail: { code: "resume_version_not_found", message: "Resume version not found." } }, 404),
      ),
    );

    await expect(getGeneralAssessment("v1")).rejects.toMatchObject({
      code: "resume_version_not_found",
      status: 404,
    });
  });

  it("creates an assessment with an empty POST", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ id: "a" }));
    vi.stubGlobal("fetch", fetchMock);

    await createGeneralAssessment("v1");

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/resumes\/versions\/v1\/general-assessment$/);
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
  });

  it("submits decisions to the review endpoint", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ id: "r" }));
    vi.stubGlobal("fetch", fetchMock);

    await submitGeneralReview("v1", "a1", [{ improvement_id: "i", action: "reject" }]);

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/resumes\/versions\/v1\/general-assessment\/a1\/review$/);
    expect(JSON.parse(init.body as string)).toEqual({
      decisions: [{ improvement_id: "i", action: "reject" }],
    });
  });

  it("maps { code, message } errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({ detail: { code: "truth_confirmation_required", message: "Confirm it." } }, 422),
      ),
    );

    const error = await submitGeneralReview("v1", "a1", []).catch((e) => e);
    expect(error).toBeInstanceOf(GeneralResumeError);
    expect(error.code).toBe("truth_confirmation_required");
    expect(error.message).toBe("Confirm it.");
  });

  it("retries a recheck by review id", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ id: "r" }));
    vi.stubGlobal("fetch", fetchMock);

    await retryGeneralRecheck("r1");

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toMatch(/\/resumes\/general-reviews\/r1\/recheck$/);
    expect(init.method).toBe("POST");
  });

  // AJI-035 — this fixed 150s timeout was not previously covered: every
  // General Resume call aborts on its own after REQUEST_TIMEOUT_MS, unlike
  // lib/jobs.ts's untimed calls, and this value is intentionally not
  // configurable per call (see docs/CODEBASE_MAP.md).
  it("rejects with GeneralResumeError once its fixed 150-second timeout elapses on a hung request", async () => {
    vi.useFakeTimers();
    const hungFetch = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new DOMException("The operation was aborted.", "AbortError"));
          });
        }),
    );
    vi.stubGlobal("fetch", hungFetch);

    const pending = createGeneralAssessment("v1");
    const assertion = expect(pending).rejects.toMatchObject({
      message: "The request took too long to respond. Please try again.",
      code: "network_error",
      status: 0,
    });

    await vi.advanceTimersByTimeAsync(150_000);
    await assertion;
    vi.useRealTimers();
  });

  it("does not time out before 150 seconds", async () => {
    vi.useFakeTimers();
    const hungFetch = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new DOMException("The operation was aborted.", "AbortError"));
          });
        }),
    );
    vi.stubGlobal("fetch", hungFetch);

    const pending = createGeneralAssessment("v1");
    const settled = { done: false };
    pending.catch(() => {
      settled.done = true;
    });

    await vi.advanceTimersByTimeAsync(149_000);
    expect(settled.done).toBe(false);

    await vi.advanceTimersByTimeAsync(1_000);
    await pending.catch(() => undefined);
    expect(settled.done).toBe(true);
    vi.useRealTimers();
  });
});
