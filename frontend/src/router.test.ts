import { describe, expect, it } from "vitest";
import { createMemoryHistory } from "vue-router";

import { createAppRouter, routes } from "./router";

describe("application routes", () => {
  it("defines a named route for every workspace area", () => {
    expect(
      routes.filter((route) => route.name).map((route) => route.path),
    ).toEqual([
      "/dashboard",
      "/imports",
      "/review",
      "/transactions",
      "/rules",
      "/merchants",
      "/categories",
      "/reports",
    ]);
  });

  it("navigates directly to a workspace URL", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push("/reports");

    expect(router.currentRoute.value.name).toBe("reports");
    expect(router.currentRoute.value.path).toBe("/reports");
  });

  it("redirects unknown URLs to the dashboard", async () => {
    const router = createAppRouter(createMemoryHistory());
    await router.push("/does-not-exist");

    expect(router.currentRoute.value.name).toBe("dashboard");
    expect(router.currentRoute.value.path).toBe("/dashboard");
  });
});

