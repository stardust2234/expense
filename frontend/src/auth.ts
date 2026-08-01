import { readonly, ref } from "vue";

import { api, ApiError } from "./api/client";
import type { AuthUser } from "./types/api";

const user = ref<AuthUser | null>(null);
let checked = false;

async function ensureSession(): Promise<boolean> {
  if (checked) return user.value !== null;
  try {
    user.value = (await api.session()).user;
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) throw error;
    user.value = null;
  }
  checked = true;
  return user.value !== null;
}

async function refreshSession(): Promise<boolean> {
  checked = false;
  return ensureSession();
}

function setSession(authenticatedUser: AuthUser): void {
  user.value = authenticatedUser;
  checked = true;
}

async function logout(): Promise<void> {
  await api.logout();
  user.value = null;
  checked = true;
}

async function deleteAccount(currentPassword: string, confirmation: string): Promise<void> {
  await api.deleteAccount(currentPassword, confirmation);
  user.value = null;
  checked = true;
}

export const auth = {
  user: readonly(user),
  ensureSession,
  refreshSession,
  setSession,
  logout,
  deleteAccount,
};

if (typeof window !== "undefined") {
  window.addEventListener("folio:unauthorised", () => {
    user.value = null;
    checked = true;
  });
}

