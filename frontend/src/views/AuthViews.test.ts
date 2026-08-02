import { createApp, nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import { i18n, setAppLocale } from "../i18n";

const routerMock = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
const routeMock = vi.hoisted(() => ({ name: "login", query: {} as Record<string, string> }));
const apiMock = vi.hoisted(() => ({
  bootstrapStatus: vi.fn().mockResolvedValue({ required: false }),
  login: vi.fn(),
  register: vi.fn(),
  requestPasswordReset: vi.fn().mockResolvedValue({ status: "accepted" }),
  verifyEmail: vi.fn().mockResolvedValue(undefined),
  resendVerification: vi.fn().mockResolvedValue({ status: "accepted", development_token: null }),
  resetPassword: vi.fn().mockResolvedValue(undefined),
}));
const authMock = vi.hoisted(() => ({ setSession: vi.fn(), refreshSession: vi.fn().mockResolvedValue(true) }));

vi.mock("vue-router", () => ({ useRoute: () => routeMock, useRouter: () => routerMock }));
vi.mock("../api/client", () => ({ api: apiMock, ApiError: class extends Error { status = 500; } }));
vi.mock("../auth", () => ({ auth: authMock }));

import LoginView from "./LoginView.vue";
import ResetPasswordView from "./ResetPasswordView.vue";
import VerifyEmailView from "./VerifyEmailView.vue";

async function render(component: object, locale: "en" | "fr" = "en") {
  setAppLocale(locale);
  const host = document.createElement("div");
  document.body.append(host);
  createApp(component).use(i18n).mount(host);
  await Promise.resolve();
  await nextTick();
  return host;
}

afterEach(() => {
  document.body.innerHTML = "";
  routeMock.query = {};
  routeMock.name = "login";
  setAppLocale("en");
  vi.clearAllMocks();
});

describe("authentication views", () => {
  it("opens registration mode from the register route", async () => {
    routeMock.name = "register";
    const host = await render(LoginView);

    expect(host.textContent).toContain("Create your account");
    expect(host.querySelector('input[autocomplete="name"]')).not.toBeNull();
  });

  it("allows a reset email to be requested from login", async () => {
    const host = await render(LoginView);
    const email = host.querySelector('input[type="email"]') as HTMLInputElement;
    email.value = "person@example.com";
    email.dispatchEvent(new Event("input"));
    const forgot = [...host.querySelectorAll("button")].find((button) => button.textContent?.includes("Forgot"));
    forgot?.click();
    await Promise.resolve();
    await nextTick();
    expect(apiMock.requestPasswordReset).toHaveBeenCalledWith("person@example.com");
    expect(host.textContent).toContain("a reset email has been sent");
  });

  it("renders verification and reset pages in French", async () => {
    const verification = await render(VerifyEmailView, "fr");
    expect(verification.textContent).toContain("Vérification de l’adresse e-mail");
    verification.remove();
    const reset = await render(ResetPasswordView, "fr");
    expect(reset.textContent).toContain("Réinitialiser le mot de passe");
  });
});

