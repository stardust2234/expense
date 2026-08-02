export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api";
let csrfToken: string | null = null;

export function resetApiSecurityState(): void {
  csrfToken = null;
}

export function setApiCsrfToken(token: string | null): void {
  csrfToken = token;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? "GET").toUpperCase();
  const headers = new Headers(init?.headers);
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    if (!csrfToken) {
      const csrfResponse = await fetch(`${apiBaseUrl}/auth/csrf`, {
        credentials: "same-origin",
      });
      if (!csrfResponse.ok) {
        throw new ApiError("Could not initialise request security", csrfResponse.status);
      }
      csrfToken = ((await csrfResponse.json()) as { csrf_token: string }).csrf_token;
    }
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
  });
  if (response.status === 401 && !path.startsWith("/auth/") && typeof window !== "undefined") {
    window.dispatchEvent(new Event("folio:unauthorised"));
  }
  if (response.status === 402 && !path.startsWith("/auth/") && typeof window !== "undefined") {
    window.dispatchEvent(new Event("folio:access-expired"));
  }
  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      message = payload.detail ?? message;
    } catch {
      // Keep the status-based fallback for non-JSON errors.
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

