import { getRequestConfig } from "next-intl/server";
import { cookies, headers } from "next/headers";

import { LOCALE_COOKIE, NAMESPACES, fromAcceptLanguage, isLocale, type Locale } from "./config";

/** Locale = the saved choice (cookie), else the browser's language. No URL prefix. */
export async function currentLocale(): Promise<Locale> {
  const saved = (await cookies()).get(LOCALE_COOKIE)?.value;
  return isLocale(saved) ? saved : fromAcceptLanguage((await headers()).get("accept-language"));
}

export default getRequestConfig(async () => {
  const locale = await currentLocale();
  const parts = await Promise.all(NAMESPACES.map(async (ns) => [ns, (await import(`../messages/${locale}/${ns}.json`)).default] as const));
  return { locale, messages: Object.fromEntries(parts), timeZone: "Africa/Algiers" };
});
