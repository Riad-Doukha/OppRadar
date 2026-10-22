// Display helpers for opportunities (dashboard cards + detail page).

import { useLocale, useTranslations } from "next-intl";
import { useMemo } from "react";

import { intlLocale, type Locale } from "@/i18n/config";
import type { Schemas } from "@/lib/api/client";
import { useOptions } from "@/lib/onboarding/options";

export type MyOpportunity = Schemas["MyOpportunity"];
export type OpportunityType = MyOpportunity["type"];
export type FeedTab = Schemas["MyOpportunityPage"]["tab"];

const DAY = 24 * 60 * 60 * 1000;
const MODES = ["remote", "hybrid", "onsite"];
const LANGUAGES = ["en", "fr", "ar"];

/** Whole days from today to the deadline (negative once it has passed). */
export function daysLeft(deadline: string | null): number | null {
  if (!deadline) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((new Date(`${deadline}T00:00:00`).getTime() - today.getTime()) / DAY);
}

/** "Organizer · Algiers, Algeria · $5,000/mo" */
export function metaLine(o: Pick<MyOpportunity, "organizer" | "location" | "country" | "funding">) {
  const place = [o.location, o.country].filter((p, i, all) => p && all.indexOf(p) === i).join(", ");
  return [o.organizer, place, o.funding].filter(Boolean).join(" · ");
}

export function sourceHost(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** Labels, dates and deadline copy in the visitor's language. */
export function useOpportunityText() {
  const t = useTranslations("opportunity");
  const locale = intlLocale(useLocale() as Locale);
  const { typeLabel } = useOptions();
  return useMemo(() => {
    const formatDate = (iso: string, withYear = false) =>
      new Date(`${iso}T00:00:00`).toLocaleDateString(locale, { day: "numeric", month: "short", ...(withYear && { year: "numeric" }) });
    return {
      typeLabel,
      formatDate,
      modeLabel: (mode: string | null) => (mode ? (MODES.includes(mode) ? t(`mode.${mode as "remote"}`) : mode) : null),
      languageLabel: (code: string) => (LANGUAGES.includes(code) ? t(`language.${code as "en"}`) : code.toUpperCase()),
      scamFlag: (flag: string) => (t.has(`flags.${flag as "application_fee"}`) ? t(`flags.${flag as "application_fee"}`) : flag),
      /** "Closes 12 Mar · 8 days left" + whether it is urgent (≤ 7 days). */
      deadlineText: (deadline: string | null): { text: string; urgent: boolean } => {
        const days = daysLeft(deadline);
        if (!deadline || days === null) return { text: t("deadline.rolling"), urgent: false };
        if (days < 0) return { text: t("deadline.closed", { date: formatDate(deadline) }), urgent: false };
        return { text: t("deadline.closes", { date: formatDate(deadline), left: t("deadline.left", { days }) }), urgent: days <= 7 };
      },
    };
  }, [t, locale, typeLabel]);
}
