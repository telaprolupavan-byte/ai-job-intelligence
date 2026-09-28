export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// AJI-035 — shared JSON transport primitive: the one place every JSON
// client (apiRequest below, lib/jobs.ts, lib/general-resume.ts) does the
// actual `fetch` + safe JSON parse. It takes the caller's fully-assembled
// URL and RequestInit (headers, signal, body, cache, ...) as-is and makes
// no decisions about auth, timeouts, base-URL/env resolution, or what
// counts as success - those stay with each caller, since they differ
// (deliberately, see docs/CODEBASE_MAP.md) across clients. A non-ok HTTP
// response is returned, not thrown, so each caller can build its own
// domain error (ApiError, GeneralResumeError, ResumeImprovementError, or a
// plain Error) from `data`. Only a genuine transport failure (network
// error, or the caller's own AbortController firing) throws here, and it
// throws unmodified - callers already decide how to interpret that.
export async function requestJson(
  url: string,
  options: RequestInit = {},
): Promise<{ response: Response; data: unknown }> {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => null);
  return { response, data };
}

// AJI-035 — shared Blob transport primitive, kept separate from
// `requestJson` because a file response is never JSON: parsing it as JSON
// would corrupt the downloaded file. `errorMessage` is supplied by the
// caller (never read from the response body) so today's one caller,
// lib/resumes.ts's fetchResumeVersionFile, keeps producing exactly
// `ApiError("Unable to retrieve the resume file.", status)` on failure,
// never exposing the backend's own error detail.
export async function blobRequest(
  url: string,
  options: RequestInit,
  errorMessage: string,
): Promise<Blob> {
  const response = await fetch(url, options);

  if (!response.ok) {
    throw new ApiError(errorMessage, response.status);
  }

  return response.blob();
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  // Bounds how long this call can leave a caller's "loading" state true.
  // Without this, a request the browser never gets a response for (a
  // proxy/gateway between the browser and the API that swallows the
  // connection instead of forwarding a slow backend's eventual response,
  // for example) leaves the returned promise pending forever - callers
  // relying on try/finally to clear a loading flag never get there.
  timeoutMs?: number,
): Promise<T> {
  // Let the browser set the multipart boundary itself for FormData bodies.
  const isFormData = options.body instanceof FormData;

  const controller = timeoutMs ? new AbortController() : null;
  const timer = controller
    ? setTimeout(() => controller.abort(), timeoutMs)
    : null;

  let result: { response: Response; data: unknown };

  try {
    result = await requestJson(`${API_URL}${path}`, {
      ...options,
      signal: controller?.signal ?? options.signal,
      headers: {
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        ...(options.headers ?? {}),
      },
    });
  } catch (err) {
    if (controller?.signal.aborted) {
      throw new ApiError(
        "The request took too long to respond. Please try again.",
        0,
      );
    }

    throw err;
  } finally {
    if (timer) {
      clearTimeout(timer);
    }
  }

  const { response, data } = result;

  if (!response.ok) {
    const message =
      (data as { detail?: unknown } | null)?.detail ??
      "Something went wrong. Please try again.";

    throw new ApiError(
      typeof message === "string"
        ? message
        : (message as { message?: string } | null)?.message ??
            "Something went wrong. Please try again.",
      response.status,
    );
  }

  return data as T;
}
