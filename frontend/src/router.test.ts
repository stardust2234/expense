import { describe, expect, it } from "vitest";
import { createMemoryHistory } from "vue-router";

import { createAppRouter, routes } from "./router";

describe("application routes", () => {
  it("defines a named route for every workspace area", () => {
    expect(
      routes.filter((route) => route.name).map((route) => route.path),
    ).toEqual([
      "/login",
      "/verify-email",
      "/reset-password",
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
});

