import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { PublicHeader } from "@/components/brand/public-header";
import { intlLocale, type Locale } from "@/i18n/config";
import { env } from "@/lib/env";

const SECTIONS = { terms: 5, privacy: 6 } as const;
const UPDATED = new Date("2026-10-25");

/** Terms / privacy text (EN/FR/AR), marked as a draft until it has been reviewed. */
export async function LegalPage({ doc }: { doc: keyof typeof SECTIONS }) {
  const t = await getTranslations("legal");
  const locale = (await getLocale()) as Locale;
  const other = doc === "terms" ? "privacy" : "terms";
  return (
    <div className="min-h-dvh bg-page">
      <PublicHeader active="home" />
      <main className="mx-auto max-w-[760px] px-4 py-10 md:py-14">
        <h1 className="font-display text-[28px] font-bold tracking-[-0.5px] text-ink md:text-[36px]">{t(`${doc}.title`)}</h1>
        <p className="pt-2 text-sm text-muted">{t("updated", { date: UPDATED.toLocaleDateString(intlLocale(locale), { dateStyle: "long" }) })}</p>
        <p role="note" className="mt-4 rounded-field border border-warning-line bg-warning-tint px-4 py-3 text-sm text-ink">
          {t("draft")}
        </p>
        {Array.from({ length: SECTIONS[doc] }, (_, i) => i + 1).map((n) => (
          <section key={n} className="pt-8">
            <h2 className="font-display text-xl font-bold text-ink">{t(`${doc}.s${n}t` as never)}</h2>
            <p className="pt-2 text-[15px] leading-relaxed text-body">{t(`${doc}.s${n}` as never)}</p>
          </section>
        ))}
        <div className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-line pt-6 text-sm">
          {env.contactEmail && <span className="text-muted">{t("contact", { email: env.contactEmail })}</span>}
          <Link href={`/${other}`} className="font-bold text-brand hover:text-brand-strong">
            {t(`${other}.title`)} <span className="inline-block rtl:-scale-x-100">→</span>
          </Link>
        </div>
      </main>
    </div>
  );
}
