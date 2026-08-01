import { describe, expect, it } from "vitest";

import { defaultCurrencyForLocale } from "./currency";

describe("locale currency defaults", () => {
  it("defaults French to euros and English to pounds", () => {
    expect(defaultCurrencyForLocale("fr")).toBe("EUR");
    expect(defaultCurrencyForLocale("en")).toBe("GBP");
  });

  it("falls back to pounds for an unsupported locale", () => {
    expect(defaultCurrencyForLocale("de")).toBe("GBP");
  });
});

