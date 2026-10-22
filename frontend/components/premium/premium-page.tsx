"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";

import { Alert } from "@/components/ui/alert";
import { ButtonLink } from "@/components/ui/button";
import { SectionLabel } from "@/components/ui/inputs";
import { Skeleton } from "@/components/ui/skeleton";
import { COMPARE, PAYMENT_METHODS, PLAN_FEATURES, PRICES, isLiteralCell, useAmount, useDzd, usePremium } from "@/lib/premium";
import { cn } from "@/lib/utils";

import { ComingSoonNotice, PreviewPill } from "./coming-soon";

const muted = (c: React.ReactNode) => <span className="text-sm font-normal text-muted">{c}</span>;

/** Premium (Figma "packs preview"), clearly labelled as coming soon. */
export function PremiumPage() {
  const t = useTranslations("premium");
  const amount = useAmount();
  const dzd = useDzd();
  const premium = usePremium();
  const reservation = premium.data?.reservation;
  const arrow = <span className="inline-block rtl:-scale-x-100">→</span>;

  return (
    <div className="mx-auto max-w-[1000px]">
      <div className="flex flex-col items-center text-center">
        <PreviewPill />
        <h1 className="pt-4 font-display text-3xl font-bold tracking-[-0.5px] text-ink sm:text-[40px]">{t("hero.title")}</h1>
        <p className="max-w-[520px] pt-2 text-[15px] text-body">{t("hero.body")}</p>
      </div>

      <ComingSoonNotice className="mt-6" />
      {premium.isError && <Alert className="mt-4">{t("loadError", { error: premium.error.message })}</Alert>}
      {reservation && (
        <Alert tone="info" className="mt-4">
          {t.rich("reservedBanner", {
            plan: t(`plans.${reservation.plan}`),
            position: reservation.position,
            strong: (c) => <strong>{c}</strong>,
            link: (c) => (
              <Link href="/premium/reserved" className="font-bold text-brand underline">
                {c}
              </Link>
            ),
          })}
        </Alert>
      )}

      <div className="grid gap-4 pt-6 lg:grid-cols-3">
        {/* Free */}
        <section className="flex flex-col rounded-card border border-line bg-surface p-6">
          <SectionLabel>{t("plans.free")}</SectionLabel>
          <p className="pt-2 font-display text-4xl font-bold text-ink">{t.rich("free.price", { muted })}</p>
          <p className="pt-1 text-sm text-body">{t("free.body")}</p>
          <Features plan="free" />
          <p className="mt-auto pt-6 text-center text-sm font-bold text-ink">{t("free.current")}</p>
        </section>

        {/* Premium */}
        <section className="relative flex flex-col rounded-card border-2 border-brand bg-surface p-6 shadow-card">
          <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-signal px-3 py-0.5 text-xs font-bold text-on-signal">{t("comingSoon")}</span>
          <div className="flex items-center justify-between">
            <SectionLabel className="text-brand">{t("plans.premium")}</SectionLabel>
            <span className="rounded-full bg-brand px-2.5 py-0.5 text-xs font-bold text-white">{t("forStudents")}</span>
          </div>
          <p className="pt-2 font-display text-4xl font-bold text-ink">{t.rich("perMonthPlanned", { amount: amount(PRICES.premium.monthly), muted })}</p>
          <p className="pt-1 text-sm text-body">{t("yearlyPlanned", { price: dzd(PRICES.premium.yearly) })}</p>
          <Features plan="premium" soon />
          <div className="mt-auto pt-6">
            {premium.isPending ? (
              <Skeleton className="h-12 w-full rounded-field" />
            ) : reservation?.plan === "premium" ? (
              <ButtonLink href="/premium/reserved" variant="outline" size="md" block>
                {t("reserved")}
              </ButtonLink>
            ) : (
              <ButtonLink href="/premium/checkout?plan=premium" size="md" block className="bg-signal text-on-signal hover:bg-signal-hover">
                {t("reserve")} {arrow}
              </ButtonLink>
            )}
            <p className="pt-2 text-center text-xs text-muted">{t("freeReservation")}</p>
          </div>
        </section>

        {/* Clubs */}
        <section className="flex flex-col rounded-card border border-line bg-surface p-6">
          <div className="flex items-center justify-between">
            <SectionLabel>{t("plans.clubs")}</SectionLabel>
            <span className="rounded-full bg-line px-2.5 py-0.5 text-xs font-bold text-muted">{t("comingSoonChip")}</span>
          </div>
          <p className="pt-2 font-display text-4xl font-bold text-ink">{t.rich("perMonthPlanned", { amount: amount(PRICES.clubs.monthly), muted })}</p>
          <p className="pt-1 text-sm text-body">{t("clubsBody")}</p>
          <Features plan="clubs" soon />
          <div className="mt-auto pt-6">
            {reservation?.plan === "clubs" ? (
              <ButtonLink href="/premium/reserved" variant="outline" size="md" block>
                {t("onWaitlist")}
              </ButtonLink>
            ) : (
              <ButtonLink href="/premium/checkout?plan=clubs" variant="outline" size="md" block>
                {t("joinWaitlist")}
              </ButtonLink>
            )}
            <p className="pt-2 text-center text-xs text-muted">{t("afterPremium")}</p>
          </div>
        </section>
      </div>

      <section className="mt-6 overflow-x-auto rounded-card border border-line bg-surface p-5 sm:p-7">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-lg font-bold text-ink">{t("compare.title")}</h2>
          <p className="text-xs text-muted">{t("compare.note")}</p>
        </div>
        <table className="mt-4 w-full min-w-[560px] text-start text-sm">
          <thead>
            <tr className="font-mono text-[11px] tracking-[1px] text-muted uppercase">
              <th className="pb-2 text-start font-normal">{t("compare.feature")}</th>
              <th className="pb-2 text-start font-normal">{t("plans.free")}</th>
              <th className="pb-2 text-start font-normal text-brand">{t("compare.premiumSoon")}</th>
              <th className="pb-2 text-start font-normal">{t("compare.clubsSoon")}</th>
            </tr>
          </thead>
          <tbody>
            {COMPARE.map((r) => (
              <tr key={r.row} className="border-t border-line">
                <td className="py-3 text-ink">{t(`compare.rows.${r.row}`)}</td>
                {(["free", "premium", "clubs"] as const).map((plan) => {
                  const cell = r[plan];
                  const text = isLiteralCell(cell) ? cell : t(`compare.cells.${cell}`);
                  return (
                    <td
                      key={plan}
                      className={cn(
                        "py-3 font-mono text-[13px]",
                        text.startsWith("✓") ? "text-success" : text === "—" ? "text-muted" : plan === "premium" ? "font-bold text-brand" : "text-ink",
                      )}
                    >
                      {text}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        <p className="pt-3 text-xs text-muted">{t("compare.agentNote")}</p>
      </section>

      <section className="mt-4 flex flex-col gap-3 rounded-card border border-dashed border-line bg-surface px-5 py-4 sm:flex-row sm:items-center">
        <div className="flex-1">
          <SectionLabel>{t("methods.title")}</SectionLabel>
          <p className="pt-1.5 text-[13px] text-body">{t("methods.body")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {PAYMENT_METHODS.map((m) => (
            <span key={m} className="rounded-full border border-line px-3 py-1 font-mono text-xs font-bold text-muted uppercase">
              {m}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}

function Features({ plan, soon }: { plan: keyof typeof PLAN_FEATURES; soon?: boolean }) {
  const t = useTranslations("premium");
  return (
    <ul className="mt-4 flex flex-col gap-2 border-t border-line pt-4 text-sm text-ink">
      {PLAN_FEATURES[plan].map((f) => (
        <li key={f} className="flex gap-2">
          <span className={soon ? "text-muted" : "text-success"} aria-hidden>
            {soon ? "○" : "✓"}
          </span>
          <span>
            {t(`features.${plan}.${f}` as Parameters<typeof t>[0])}
            {soon && <span className="sr-only"> {t("soonSr")}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}
