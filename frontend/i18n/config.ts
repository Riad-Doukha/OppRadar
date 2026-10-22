// Server-safe: shared by middleware-free request config, the layout and client code.

export const LOCALES = ["en", "fr", "ar"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";
export const LOCALE_COOKIE = "NEXT_LOCALE";

export const LOCALE_NAMES: Record<Locale, string> = { en: "English", fr: "Français", ar: "العربية" };

export const isLocale = (v: unknown): v is Locale => LOCALES.includes(v as Locale);
export const dirOf = (l: Locale) => (l === "ar" ? "rtl" : "ltr");

/**
 * Locale for Intl date/number formatting. Algerian conventions: ar-DZ keeps
 * Latin digits (what users see on prices and dates here), fr-DZ uses DZD.
 */
export const intlLocale = (l: Locale) => ({ en: "en-GB", fr: "fr-DZ", ar: "ar-DZ" })[l];

/** First supported language in an Accept-Language header, for a first visit. */
export function fromAcceptLanguage(header: string | null): Locale {
  for (const part of (header ?? "").split(",")) {
    const tag = part.split(";")[0].trim().slice(0, 2).toLowerCase();
    if (isLocale(tag)) return tag;
  }
  return DEFAULT_LOCALE;
}

/** Message files, one JSON per namespace per locale (messages/<locale>/<ns>.json). */
export const NAMESPACES = [
  "common",
  "landing",
  "auth",
  "onboarding",
  "options",
  "shell",
  "dashboard",
  "opportunity",
  "profile",
  "settings",
  "notifications",
  "agent",
  "apply",
  "applications",
  "premium",
  "submit",
  "admin",
  "explore",
] as const;
