"use client";

import { setLocale } from "@/i18n/actions";
import type { Locale } from "@/i18n/config";
import { api } from "@/lib/api/client";

/** Switch the interface language (cookie) and, when signed in, save it on the
 * profile so emails use it too. A failed save (signed out, demo) is ignored. */
export async function changeLocale(locale: Locale) {
  await setLocale(locale);
  await api("/me/settings", { method: "PATCH", body: JSON.stringify({ locale }) }).catch(() => {});
}
