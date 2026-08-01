import type { AuthSession } from "../types/api";
import { request, setApiCsrfToken } from "./request";

export type AdminUser = {
  id: number;
  email: string;
  display_name: string;
  is_admin: boolean;
  is_active: boolean;
  email_verified_at: string | null;
};

export type AuditEvent = {
  id: number;
  event_type: string;
  actor_user_id: number | null;
  target_user_id: number | null;
  details: Record<string, unknown>;
  created_at: string;
};

export const authApi = {
  session: () => request<AuthSession>("/auth/session"),
  bootstrapStatus: () => request<{ required: boolean }>("/auth/bootstrap-status"),
  verifyEmail: (token: string) => request<void>("/auth/verify-email", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token }) }),
  resendVerification: () => request<{ status: string; development_token: string | null }>("/auth/verification/resend", { method: "POST" }),
  requestPasswordReset: (email: string) => request("/auth/password-reset/request", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) }),
  resetPassword: (token: string, newPassword: string) => request<void>("/auth/password-reset/confirm", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token, new_password: newPassword }) }),
  login: async (email: string, password: string) => {
    const session = await request<AuthSession>("/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) });
    setApiCsrfToken(session.csrf_token);
    return session;
  },
  register: async (email: string, displayName: string, password: string, bootstrapToken: string | null = null) => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (bootstrapToken) headers["X-Admin-Bootstrap-Token"] = bootstrapToken;
    const session = await request<AuthSession>("/auth/register", { method: "POST", headers, body: JSON.stringify({ email, display_name: displayName, password }) });
    setApiCsrfToken(session.csrf_token);
    return session;
  },
  logout: async () => {
    await request<void>("/auth/logout", { method: "POST" });
    setApiCsrfToken(null);
  },
  changePassword: (currentPassword: string, newPassword: string) => request<void>("/auth/password/change", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) }),
  changeEmail: (email: string, currentPassword: string) => request<{ status: string; development_token: string | null }>("/auth/account/email", { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, current_password: currentPassword }) }),
  deleteAccount: (currentPassword: string, confirmation: string) => request<void>("/auth/account", { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ current_password: currentPassword, confirmation }) }),
  adminUsers: () => request<AdminUser[]>("/auth/admin/users"),
  updateAdminUser: (id: number, changes: { is_admin?: boolean; is_active?: boolean }) => request<AdminUser>(`/auth/admin/users/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes) }),
  adminAudit: () => request<AuditEvent[]>("/auth/admin/audit"),
};

