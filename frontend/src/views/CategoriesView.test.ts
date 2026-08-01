import { createApp, nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import { i18n, setAppLocale } from "../i18n";

const apiMock = vi.hoisted(() => ({
  categories: vi.fn().mockResolvedValue([
    { id: 1, code: "housing", name: "Housing", parent_category_id: null, default_priority: "protected" },
    { id: 2, code: "housing.rent", name: "Rent", parent_category_id: 1, default_priority: "protected" },
    { id: 3, code: null, name: "My custom category", parent_category_id: null, default_priority: "adjustable" },
  ]),
  createCategory: vi.fn(),
  updateCategory: vi.fn(),
  deleteCategory: vi.fn(),
}));

vi.mock("../api/client", () => ({ api: apiMock }));

import CategoriesView from "./CategoriesView.vue";

async function render(locale: "en" | "fr") {
  setAppLocale(locale);
  const host = document.createElement("div");
  document.body.append(host);
  createApp(CategoriesView).use(i18n).mount(host);
  await Promise.resolve();
  await nextTick();
  return host;
}

afterEach(() => {
  setAppLocale("en");
  document.body.innerHTML = "";
});

describe("category localisation", () => {
  it("renders seeded codes and custom names in English", async () => {
    const host = await render("en");
    expect(host.textContent).toContain("Categories");
    expect((host.querySelector('input[readonly]') as HTMLInputElement).value).toBe("Housing");
    expect([...host.querySelectorAll<HTMLInputElement>("input")].some((input) => input.value === "My custom category")).toBe(true);
  });

  it("renders seeded codes in French without translating custom names", async () => {
    const host = await render("fr");
    const values = [...host.querySelectorAll<HTMLInputElement>('input[readonly]')].map((input) => input.value);
    expect(host.textContent).toContain("Catégories");
    expect(values).toEqual(["Logement", "Loyer"]);
    expect([...host.querySelectorAll<HTMLInputElement>("input")].some((input) => input.value === "My custom category")).toBe(true);
  });
});

