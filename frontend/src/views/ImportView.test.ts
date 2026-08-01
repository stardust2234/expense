import { createApp, nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

import { i18n, setAppLocale } from "../i18n";

const apiMock = vi.hoisted(() => ({
  importHistory: vi.fn().mockResolvedValue({ items: [], total: 0, limit: 25, offset: 0 }),
}));

vi.mock("../api/client", () => ({ api: apiMock }));

import ImportView from "./ImportView.vue";

async function mountView() {
  const host = document.createElement("div");
  document.body.append(host);
  createApp(ImportView).use(i18n).mount(host);
  await Promise.resolve();
  await nextTick();
  return host;
}

afterEach(() => {
  setAppLocale("en");
  document.body.innerHTML = "";
});

describe("import currency default", () => {
  it("uses EUR in French and follows a locale change while untouched", async () => {
    setAppLocale("fr");
    const host = await mountView();
    const currency = host.querySelector('input[maxlength="3"]') as HTMLInputElement;
    expect(currency.value).toBe("EUR");

    setAppLocale("en");
    await nextTick();
    expect(currency.value).toBe("GBP");
  });

  it("does not overwrite a currency entered by the user", async () => {
    setAppLocale("fr");
    const host = await mountView();
    const currency = host.querySelector('input[maxlength="3"]') as HTMLInputElement;
    currency.value = "USD";
    currency.dispatchEvent(new Event("input", { bubbles: true }));

    setAppLocale("en");
    await nextTick();
    expect(currency.value).toBe("USD");
  });
});

