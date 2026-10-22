"use server";

import { cookies } from "next/headers";

import { LOCALE_COOKIE, isLocale } from "./config";

/** Saves the interface language for this browser (one year). */
export async function setLocale(locale: string) {
  if (!isLocale(locale)) return;
  (await cookies()).set(LOCALE_COOKIE, locale, { path: "/", maxAge: 60 * 60 * 24 * 365, sameSite: "lax" });
}
