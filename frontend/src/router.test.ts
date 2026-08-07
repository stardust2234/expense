import { describe, expect, it, vi } from "vitest";
import { createMemoryHistory } from "vue-router";

import { createAppRouter, routes } from "./router";

describe("application routes", () => {
  it("defines a named route for every workspace area", () => {
    expect(
      routes.filter((route) => route.name).map((route) => route.path),
    ).toEqual([
      "/",
      "/login",
      "/register",
      "/dashboard",
      "/account",
      "/imports",
      "/plan",
      "/review",
      "/transactions",
      "/rules",
      "/merchants",
      "/categories",
      "/reports",
    ]);
  });

  it("keeps the landing, login, and registration pages public", async () => {
    const router = createAppRouter(createMemoryHistory(), async () => false);
    await router.push("/");
    expect(router.currentRoute.value.name).toBe("landing");
    await router.push("/register");
    expect(router.currentRoute.value.name).toBe("register");
  });

  it("navigates directly to a workspace URL", async () => {
    const router = createAppRouter(createMemoryHistory(), async () => true);
    await router.push("/reports");

    expect(router.currentRoute.value.name).toBe("reports");
    expect(router.currentRoute.value.path).toBe("/reports");
  });

  it("redirects unknown URLs to the dashboard", async () => {
    const router = createAppRouter(createMemoryHistory(), async () => true);
    await router.push("/does-not-exist");

    expect(router.currentRoute.value.name).toBe("dashboard");
    expect(router.currentRoute.value.path).toBe("/dashboard");
  });

  it("redirects an unauthenticated workspace route to login", async () => {
    const router = createAppRouter(createMemoryHistory(), async () => false);
    await router.push("/reports");

    expect(router.currentRoute.value.name).toBe("login");
    expect(router.currentRoute.value.query.redirect).toBe("/reports");
  });

  it("redirects an expired trial to pricing but leaves account access available", async () => {
    let currentUser = {
      id: 1,
      email: "person@example.com",
      display_name: "Person",
      workspace_id: 1,
      trial_ends_at: "2026-01-01T00:00:00Z",
      access_expires_at: null,
      access_active: false,
    };
    const router = createAppRouter(createMemoryHistory(), async () => true, () => currentUser);

    await router.push("/reports");
    expect(router.currentRoute.value.name).toBe("landing");
    expect(router.currentRoute.value.hash).toBe("#pricing");

    await router.push("/account");
    expect(router.currentRoute.value.name).toBe("account");
    currentUser = { ...currentUser, access_active: true };
  });

  it("handles errors raised while checking a route session", async () => {
    const error = new Error("Session service unavailable");
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const router = createAppRouter(createMemoryHistory(), async () => Promise.reject(error));

    await expect(router.push("/reports")).rejects.toThrow("Session service unavailable");

    expect(consoleError).toHaveBeenCalledWith("Route navigation to /reports failed", error);
    consoleError.mockRestore();
  });
});

