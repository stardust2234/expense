import { createApp, nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import { i18n } from "../i18n";

const logout = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));

vi.mock("@auth0/auth0-vue", () => ({
  useAuth0: () => ({
    isAuthenticated: true,
    isLoading: false,
    logout,
    user: { name: "Owner", email: "owner@example.com" },
  }),
}));

import LogoutButton from "./LogoutButton.vue";
import UserProfile from "./UserProfile.vue";

function mount(component: Parameters<typeof createApp>[0]) {
  const host = document.createElement("div");
  document.body.append(host);
  createApp(component).use(i18n).mount(host);
  return host;
}

afterEach(() => {
  document.body.innerHTML = "";
  vi.clearAllMocks();
});

describe("Auth0 account components", () => {
  it("logs out through Auth0 and returns to the current origin", async () => {
    const host = mount(LogoutButton);
    (host.querySelector("button") as HTMLButtonElement).click();
    await nextTick();

    expect(logout).toHaveBeenCalledWith({
      logoutParams: { returnTo: window.location.origin },
    });
  });

  it("renders the authenticated Auth0 profile", () => {
    const host = mount(UserProfile);

    expect(host.textContent).toContain("Owner");
    expect(host.textContent).toContain("owner@example.com");
    expect(host.querySelector("img")?.getAttribute("src")).toContain("data:image/svg+xml");
  });
});

