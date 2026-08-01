import type { AppLocale } from "../i18n";

export function defaultCurrencyForLocale(locale: AppLocale | string): "EUR" | "GBP" {
  return locale === "fr" ? "EUR" : "GBP";
}

