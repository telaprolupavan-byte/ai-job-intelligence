import { afterEach, describe, expect, it, vi } from "vitest";
import { apiRequest, ApiError } from "./api";

describe("apiRequest timeout", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("rejects a hung request once timeoutMs elapses, instead of leaving the caller's promise pending forever", async () => {
    // Simulates a request the browser never gets a response for (e.g. a
    // proxy/gateway between the browser and the API swallowing the
    // connection while the backend is still working) - the only thing
    // that ever settles this fetch is the abort signal, exactly like the
    // real fetch/AbortController contract.
    const hungFetch = vi.fn(
      (_url: string, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new DOMException("The operation was aborted.", "AbortError"));
          });
        }),
    );
    vi.stubGlobal("fetch", hungFetch);

    const start = Date.now();

    await expect(
      apiRequest("/resumes/versions/x/ai-analysis", { method: "POST" }, 50),
    ).rejects.toMatchObject({
      message: "The request took too long to respond. Please try again.",
    });

    // The rejection must come from our own timeout, not from the test
    // runner's default timeout - it should land right around timeoutMs.
    expect(Date.now() - start).toBeLessThan(1000);
  });

  it("still resolves normally when no timeoutMs is given and the response arrives quickly", async () => {
    const okFetch = vi.fn(
      async () =>
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", okFetch);

    await expect(apiRequest("/health", { method: "GET" })).resolves.toEqual({
      ok: true,
    });
  });

  it("still rejects with the backend's own error once it responds, even under a timeout budget", async () => {
    const errorFetch = vi.fn(
      async () =>
        new Response(JSON.stringify({ detail: "OpenAI request timed out." }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        }),
    );
    vi.stubGlobal("fetch", errorFetch);

    const error: unknown = await apiRequest(
      "/resumes/versions/x/ai-analysis",
      { method: "POST" },
      50_000,
    ).catch((err: unknown) => err);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe("OpenAI request timed out.");
    expect((error as ApiError).status).toBe(503);
  });
});
