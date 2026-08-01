import { createI18n } from "vue-i18n";

import en from "./locales/en.json";
import fr from "./locales/fr.json";

export const supportedLocales = ["en", "fr"] as const;
export type AppLocale = (typeof supportedLocales)[number];
export const LOCALE_STORAGE_KEY = "expense-tracker.locale";

function isAppLocale(value: string | null | undefined): value is AppLocale {
  return supportedLocales.includes(value as AppLocale);
}

export function resolveInitialLocale(
  storedLocale: string | null | undefined,
  browserLocale: string | null | undefined,
): AppLocale {
  if (isAppLocale(storedLocale)) return storedLocale;
  return browserLocale?.toLowerCase().startsWith("fr") ? "fr" : "en";
}

function initialLocale(): AppLocale {
  const storedLocale = typeof localStorage === "undefined"
    ? null
    : localStorage.getItem(LOCALE_STORAGE_KEY);
  const browserLocale = typeof navigator === "undefined" ? null : navigator.language;
  return resolveInitialLocale(storedLocale, browserLocale);
}

export const i18n = createI18n({
  legacy: false,
  locale: initialLocale(),
  fallbackLocale: "en",
  messages: { en, fr },
  datetimeFormats: {
    en: { medium: { year: "numeric", month: "short", day: "numeric" } },
    fr: { medium: { year: "numeric", month: "short", day: "numeric" } },
  },
});

export function setAppLocale(locale: AppLocale): void {
  i18n.global.locale.value = locale;
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  }
  if (typeof document !== "undefined") {
    document.documentElement.lang = locale;
  }
}

setAppLocale(i18n.global.locale.value);

