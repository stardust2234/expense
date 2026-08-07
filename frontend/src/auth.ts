import type { Auth0Plugin } from "@auth0/auth0-vue";
import { readonly, ref } from "vue";

import { api } from "./api/client";
import { setAccessTokenProvider } from "./api/request";
import type { AuthUser } from "./types/api";

const user = ref<AuthUser | null>(null);
let client: Auth0Plugin | null = null;

export function configureAuth0(auth0: Auth0Plugin): void {
  client = auth0;
  setAccessTokenProvider(() => auth0.getAccessTokenSilently());
}

async function waitUntilLoaded(): Promise<void> {
  while (client?.isLoading.value) await new Promise((resolve) => setTimeout(resolve, 10));
}

async function ensureSession(): Promise<boolean> {
  if (!client) return false;
  await waitUntilLoaded();
  if (!client.isAuthenticated.value) {
    user.value = null;
    return false;
  }
  user.value = await api.me();
  return true;
}

export const auth = { user: readonly(user), ensureSession };

