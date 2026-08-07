import { createApp, nextTick } from "vue";
import { describe, expect, it, vi } from "vitest";

import { i18n } from "../i18n";

vi.mock("@auth0/auth0-vue", () => ({
  useAuth0: () => ({
    user: { name: "Owner", email: "owner@example.com" },
    isAuthenticated: true,
    isLoading: false,
  }),
}));

import AccountView from "./AccountView.vue";

describe("Auth0 account profile", () => {
  it("shows the Auth0-managed identity", async () => {
    const host = document.createElement("div");
    createApp(AccountView).use(i18n).mount(host);
    await nextTick();
    expect(host.textContent).toContain("Owner");
    expect(host.textContent).toContain("owner@example.com");
    expect(host.textContent).toContain("managed by Auth0");
    expect(host.querySelector("form")).toBeNull();
  });
});

