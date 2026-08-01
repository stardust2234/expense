import { createApp, nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import { i18n, setAppLocale } from "../i18n";

const routerMock = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
const authMock = vi.hoisted(() => ({
  user: { value: {
    id: 1,
    email: "owner@example.com",
    display_name: "Owner",
    is_admin: true,
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
  adminUsers: vi.fn().mockResolvedValue([{ id: 1, email: "owner@example.com", display_name: "Owner", is_admin: true, is_active: true, email_verified_at: "2026-01-01" }]),
  adminAudit: vi.fn().mockResolvedValue([]),
  updateAdminUser: vi.fn(),
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
  it("shows profile, workspace administration and no duplicate logout or sessions card", async () => {
    const host = await render();
    expect(host.textContent).toContain("owner@example.com");
    expect(host.textContent).toContain("Workspace users");
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

  it("renders destructive account controls in French", async () => {
    const host = await render("fr");
    expect(host.textContent).toContain("Supprimer le compte");
    expect(host.textContent).toContain("Supprimer mon compte et mes données");
  });
});

