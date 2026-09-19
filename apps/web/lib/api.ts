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

  let response: Response;

  try {
    response = await fetch(`${API_URL}${path}`, {
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

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      data?.detail ?? "Something went wrong. Please try again.";

    throw new ApiError(
      typeof message === "string"
        ? message
        : message?.message ?? "Something went wrong. Please try again.",
      response.status,
    );
  }

  return data as T;
}