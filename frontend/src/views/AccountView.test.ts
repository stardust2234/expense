import { createApp, nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import { i18n, setAppLocale } from "../i18n";

const routerMock = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
const authMock = vi.hoisted(() => ({
  user: { value: {
    id: 1,
    email: "owner@example.com",
    display_name: "Owner",
    workspace_id: 1,
    email_verified: true,
  } },
  setSession: vi.fn(),
  logout: vi.fn(),
  deleteAccount: vi.fn().mockResolvedValue(undefined),
}));
const apiMock = vi.hoisted(() => ({
  changePassword: vi.fn(),
  changeEmail: vi.fn().mockResolvedValue({ status: "verification_required", development_token: "token" }),
  accountAudit: vi.fn().mockResolvedValue([]),
}));

vi.mock("vue-router", () => ({ useRouter: () => routerMock }));
vi.mock("../auth", () => ({ auth: authMock }));
vi.mock("../api/client", () => ({ api: apiMock, ApiError: class extends Error {} }));

import AccountView from "./AccountView.vue";

async function render(locale: "en" | "fr" = "en") {
  setAppLocale(locale);
  const host = document.createElement("div");
  document.body.append(host);
  createApp(AccountView).use(i18n).mount(host);
  await Promise.resolve();
  await nextTick();
  return host;
}

afterEach(() => {
  document.body.innerHTML = "";
  setAppLocale("en");
  vi.clearAllMocks();
});

describe("account management", () => {
  it("shows the owner profile without workspace-user administration or duplicate logout", async () => {
    const host = await render();
    expect(host.textContent).toContain("owner@example.com");
    expect(host.textContent).not.toContain("Workspace users");
    expect(host.textContent).toContain("Security");
    expect(host.textContent).not.toContain("Active sessions");
    expect(host.textContent).not.toContain("Sign out");
  });

  it("requests email verification for an address change", async () => {
    const host = await render();
    const forms = host.querySelectorAll("form");
    const emailForm = forms[1];
    const inputs = emailForm.querySelectorAll("input");
    (inputs[0] as HTMLInputElement).value = "new@example.com";
    inputs[0].dispatchEvent(new Event("input"));
    (inputs[1] as HTMLInputElement).value = "current-password";
    inputs[1].dispatchEvent(new Event("input"));
    emailForm.dispatchEvent(new Event("submit"));
    await Promise.resolve();
    await nextTick();
    expect(apiMock.changeEmail).toHaveBeenCalledWith("new@example.com", "current-password");
    expect(routerMock.push).toHaveBeenCalledWith({ name: "verify-email", query: { token: "token" } });
  });

  it("keeps the current session after changing the password", async () => {
    apiMock.changePassword.mockResolvedValueOnce(undefined);
    const host = await render();
    const passwordForm = host.querySelectorAll("form")[0];
    const inputs = passwordForm.querySelectorAll("input");
    (inputs[0] as HTMLInputElement).value = "current-password";
    inputs[0].dispatchEvent(new Event("input"));
    (inputs[1] as HTMLInputElement).value = "replacement-password";
    inputs[1].dispatchEvent(new Event("input"));
    passwordForm.dispatchEvent(new Event("submit"));
    await Promise.resolve();
    await nextTick();

    expect(apiMock.changePassword).toHaveBeenCalledWith(
      "current-password",
      "replacement-password",
    );
    expect(routerMock.replace).not.toHaveBeenCalledWith("/login");
    expect(host.textContent).toContain("Other signed-in sessions have been revoked");
  });

  it("renders destructive account controls in French", async () => {
    const host = await render("fr");
    expect(host.textContent).toContain("Supprimer le compte");
    expect(host.textContent).toContain("Supprimer mon compte et mes données");
  });
});

