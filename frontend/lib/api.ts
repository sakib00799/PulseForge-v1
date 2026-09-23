// In local development the browser talks to Next.js on the same origin. The
// rewrite in next.config.ts forwards these requests to FastAPI on port 8001.
// NEXT_PUBLIC_API_BASE_URL can still point at a public API in deployment.
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

export type User = { id: string; email: string; full_name: string; is_active: boolean };
export type Organization = { id: string; name: string; slug: string; created_at: string };
export type Membership = { organization: Organization; role: string; permissions: string[] };
export type Service = {
  id: string; organization_id: string; name: string; slug: string;
  description: string | null; environment: string; status: string;
};
export type TelemetryEvent = {
  id: string; service_id: string; event_id: string; event_type: string; level: string;
  message: string; occurred_at: string; metadata: Record<string, unknown>;
};
export type Incident = {
  id: string; service_id: string; title: string; severity: string; status: string;
  detected_at: string; acknowledged_at: string | null; resolved_at: string | null;
};
export type CreatedApiKey = { id: string; api_key: string; prefix: string; name: string };
export type SessionInfo = {
  id: string; created_at: string; expires_at: string; last_used_at: string | null;
  ip_address: string | null; user_agent: string | null;
};
export type Member = {
  id: string; user_id: string; email: string; full_name: string;
  role: "OWNER" | "ADMIN" | "ENGINEER" | "VIEWER"; joined_at: string;
};
export type AuditLog = {
  id: string; organization_id: string | null; actor_user_id: string | null;
  action: string; resource_type: string; resource_id: string | null;
  ip_address: string | null; user_agent: string | null;
  metadata: Record<string, unknown>; created_at: string;
};
export type ForgotPasswordResult = { message: string; development_reset_token?: string };

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly method: string,
    readonly path: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export function isUnauthorizedError(reason: unknown): boolean {
  return reason instanceof ApiRequestError && reason.status === 401;
}

let accessToken: string | null = null;
// Changes only when the browser signs in or signs out, not on token rotation.
let sessionGeneration = 0;

function storeAccessToken(tokens: { access_token: string }) {
  accessToken = tokens.access_token;
}

export function clearTokens() {
  sessionGeneration += 1;
  accessToken = null;
  // Remove tokens created by pre-cookie versions of the frontend.
  localStorage.removeItem("pulseforge_access");
  localStorage.removeItem("pulseforge_refresh");
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (body.error && typeof body.error.message === "string") {
      const issue = Array.isArray(body.error.details) ? body.error.details[0] : null;
      if (issue && typeof issue.message === "string") {
        return `${issue.field ?? "request"}: ${issue.message}`;
      }
      return body.error.message;
    }
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail) && body.detail.length) {
      const issue = body.detail[0];
      const field = Array.isArray(issue.loc) ? issue.loc.at(-1) : "request";
      return `${field}: ${issue.msg ?? "Invalid value"}`;
    }
    return "The submitted data is invalid";
  } catch {
    return `Request failed (${response.status})`;
  }
}

let refreshInFlight: Promise<boolean> | null = null;

async function performSessionRefresh(): Promise<boolean> {
  const generation = sessionGeneration;
  try {
    const response = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (generation !== sessionGeneration) return false;
    if (!response.ok) {
      clearTokens();
      return false;
    }
    storeAccessToken(await response.json());
    return true;
  } catch {
    if (generation === sessionGeneration) clearTokens();
    return false;
  }
}

function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = performSessionRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const requestAccessToken = accessToken;
  const requestGeneration = sessionGeneration;
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (requestAccessToken) headers.set("Authorization", `Bearer ${requestAccessToken}`);
  let response = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: "include" });
  if (response.status === 401 && retry && requestGeneration === sessionGeneration) {
    // Another request may already have refreshed the session while this one
    // was in flight. Reuse that token instead of rotating the refresh token again.
    let replacementToken = accessToken;
    if (replacementToken === requestAccessToken) {
      replacementToken = await refreshSession()
        ? accessToken
        : null;
    }
    if (replacementToken) {
      headers.set("Authorization", `Bearer ${replacementToken}`);
      response = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: "include" });
    }
  }
  if (!response.ok) {
    const method = init.method ?? "GET";
    const detail = await parseError(response);
    if (response.status === 401 && requestGeneration === sessionGeneration) clearTokens();
    throw new ApiRequestError(detail, response.status, method, path);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export async function login(email: string, password: string): Promise<void> {
  if (refreshInFlight) await refreshInFlight;
  const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    credentials: "include",
  });
  if (!response.ok) throw new Error(await parseError(response));
  sessionGeneration += 1;
  storeAccessToken(await response.json());
}

export async function register(
  fullName: string,
  email: string,
  password: string,
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ full_name: fullName, email, password }),
  });
  if (!response.ok) throw new Error(await parseError(response));
  await login(email, password);
}

export async function logout(): Promise<void> {
  if (refreshInFlight) await refreshInFlight;
  await fetch(`${API_BASE}/api/v1/auth/logout`, {
    method: "POST",
    credentials: "include",
  }).catch(() => undefined);
  clearTokens();
}

export async function forgotPassword(email: string): Promise<ForgotPasswordResult> {
  const response = await fetch(`${API_BASE}/api/v1/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
    credentials: "include",
  });
  if (!response.ok) throw new Error(await parseError(response));
  return response.json();
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/v1/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
    credentials: "include",
  });
  if (!response.ok) throw new Error(await parseError(response));
  clearTokens();
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  await api("/api/v1/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  clearTokens();
}

export async function logoutAll(): Promise<void> {
  await api("/api/v1/auth/logout-all", { method: "POST" });
  clearTokens();
}

export function listSessions(): Promise<SessionInfo[]> {
  return api<SessionInfo[]>("/api/v1/auth/sessions");
}

export function revokeSession(sessionId: string): Promise<void> {
  return api<void>(`/api/v1/auth/sessions/${sessionId}`, { method: "DELETE" });
}

export async function sendDemoEvents(apiKey: string): Promise<void> {
  const path = "/api/v1/events";
  for (let index = 1; index <= 5; index += 1) {
    const response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({
        event_id: `browser-demo-${crypto.randomUUID()}`,
        event_type: "DATABASE_TIMEOUT",
        level: index === 5 ? "CRITICAL" : "ERROR",
        message: `Payment database timed out (demo ${index}/5)`,
        occurred_at: new Date(Date.now() + index * 1000).toISOString(),
        metadata: { database: "payments-db", timeout_ms: 5000, demo: true },
      }),
    });
    if (!response.ok) {
      throw new ApiRequestError(await parseError(response), response.status, "POST", path);
    }
  }
}
