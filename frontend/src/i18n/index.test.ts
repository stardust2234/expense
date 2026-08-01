import { afterEach, describe, expect, it } from "vitest";

import {
  i18n,
  LOCALE_STORAGE_KEY,
  resolveInitialLocale,
  setAppLocale,
} from "./index";

describe("locale selection", () => {
  afterEach(() => {
    setAppLocale("en");
    localStorage.removeItem(LOCALE_STORAGE_KEY);
  });

  it("prefers a supported persisted locale", () => {
    expect(resolveInitialLocale("fr", "en-GB")).toBe("fr");
  });

  it("uses French browser preferences and otherwise falls back to English", () => {
    expect(resolveInitialLocale(null, "fr-FR")).toBe("fr");
    expect(resolveInitialLocale("de", "de-DE")).toBe("en");
  });

  it("persists changes and updates the document language", () => {
    setAppLocale("fr");

    expect(i18n.global.locale.value).toBe("fr");
    expect(localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("fr");
    expect(document.documentElement.lang).toBe("fr");
  });
});

