export const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api";
let accessTokenProvider: (() => Promise<string>) | null = null;

export function setAccessTokenProvider(provider: () => Promise<string>): void {
  accessTokenProvider = provider;
}

export function resetApiSecurityState(): void {
  accessTokenProvider = null;
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
  const headers = new Headers(init?.headers);
  if (path !== "/health") {
    if (!accessTokenProvider) throw new ApiError("Auth0 is not initialised", 401);
    headers.set("Authorization", `Bearer ${await accessTokenProvider()}`);
  }
  const response = await fetch(`${apiBaseUrl}${path}`, { ...init, headers });
  if (response.status === 401 && typeof window !== "undefined") {
    window.dispatchEvent(new Event("folio:unauthorised"));
  }
  if (response.status === 402 && typeof window !== "undefined") {
    window.dispatchEvent(new Event("folio:access-expired"));
  }
  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      message = payload.detail ?? message;
    } catch { /* use status fallback */ }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

