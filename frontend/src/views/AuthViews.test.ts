import { createApp, nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import { i18n, setAppLocale } from "../i18n";

const routeMock = vi.hoisted(() => ({ name: "login", query: {} as Record<string, string> }));
const loginWithRedirect = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));

vi.mock("vue-router", () => ({ useRoute: () => routeMock }));
vi.mock("@auth0/auth0-vue", () => ({
  useAuth0: () => ({
    loginWithRedirect,
    isLoading: false,
    error: null,
  }),
}));

import LoginView from "./LoginView.vue";

async function render() {
  const host = document.createElement("div");
  document.body.append(host);
  createApp(LoginView).use(i18n).mount(host);
  await nextTick();
  return host;
}

afterEach(() => {
  document.body.innerHTML = "";
  routeMock.name = "login";
  routeMock.query = {};
  setAppLocale("en");
  vi.clearAllMocks();
});

describe("Auth0 views", () => {
  it("opens Auth0 Universal Login", async () => {
    const host = await render();
    (host.querySelector("button") as HTMLButtonElement).click();
    await Promise.resolve();
    expect(loginWithRedirect).toHaveBeenCalled();
  });

  it("requests Auth0 signup mode from the register route", async () => {
    routeMock.name = "register";
    const host = await render();
    (host.querySelector("button") as HTMLButtonElement).click();
    await Promise.resolve();
    expect(loginWithRedirect).toHaveBeenCalledWith(
      expect.objectContaining({ authorizationParams: { screen_hint: "signup" } }),
    );
  });
});

