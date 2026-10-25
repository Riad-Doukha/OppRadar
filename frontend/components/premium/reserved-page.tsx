"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button, ButtonLink, Spinner } from "@/components/ui/button";
import { SectionLabel } from "@/components/ui/inputs";
import { Skeleton } from "@/components/ui/skeleton";
import { intlLocale, type Locale } from "@/i18n/config";
import { api, type Me } from "@/lib/api/client";
import { PRICES, useCancelReservation, useDzd, usePremium } from "@/lib/premium";

import { PreviewPill } from "./coming-soon";

/** Figma "payment success", reworded: the reservation is saved, nothing was paid. */
export function ReservedPage() {
  const t = useTranslations("premium");
  const tr = useTranslations("premium.reservedPage");
  const dzd = useDzd();
  const locale = intlLocale(useLocale() as Locale);
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  const premium = usePremium();
  const cancel = useCancelReservation();
  const [confirming, setConfirming] = useState(false);
  const r = premium.data?.reservation;

  if (premium.isPending) return <Skeleton className="mx-auto h-[420px] max-w-[560px] rounded-card" />;
  if (premium.isError) return <Alert className="mx-auto max-w-[560px]">{tr("loadError", { error: premium.error.message })}</Alert>;

  if (!r) {
    return (
      <div className="mx-auto flex max-w-[560px] flex-col items-center rounded-card border border-line bg-surface p-8 text-center">
        <PreviewPill />
        <h1 className="pt-4 text-2xl font-bold text-ink">{cancel.isSuccess ? tr("cancelled") : tr("none")}</h1>
        <p className="pt-2 text-sm text-body">{tr("noneBody")}</p>
        <ButtonLink href="/premium" size="md" className="mt-6">
          {tr("seePlans")}
        </ButtonLink>
      </div>
    );
  }

  const name = t(`plans.${r.plan}`);

  return (
    <div className="mx-auto flex max-w-[560px] flex-col items-center rounded-card border border-line bg-surface p-6 text-center shadow-card sm:p-10">
      <span className="flex size-14 items-center justify-center rounded-full bg-success-tint">
        {/* eslint-disable-next-line @next/next/no-img-element -- decorative check */}
        <img src="/icons/check-green.svg" alt="" width={26} height={26} />
      </span>
      <h1 className="pt-4 font-display text-2xl font-bold text-ink sm:text-[28px]">{tr("title")}</h1>
      <p className="pt-2 text-[15px] text-body">{tr.rich("body", { plan: name, strong: (c) => <strong>{c}</strong> })}</p>

      <div className="mt-6 w-full rounded-field bg-page p-5">
        <SectionLabel>{tr("place")}</SectionLabel>
        <p className="pt-1 font-display text-5xl font-bold text-brand">#{r.position}</p>
        <p className="pt-1 text-xs text-muted">{tr("of", { count: premium.data.reservations_total })}</p>
      </div>

      <dl className="mt-4 w-full divide-y divide-line text-start text-sm">
        <Row k={tr("plan")} v={name} />
        <Row k={tr("billing")} v={tr("billingValue", { period: t(r.billing === "yearly" ? "checkout.yearly" : "checkout.monthly"), price: dzd(PRICES[r.plan][r.billing]) })} />
        <Row k={tr("preferred")} v={r.payment_method ? t(`methods.${r.payment_method}`) : tr("notChosen")} />
        <Row k={tr("charged")} v={dzd(0)} />
        <Row k={tr("on")} v={new Date(r.created_at).toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" })} />
      </dl>

      <Alert tone="info" className="mt-4 w-full text-start">
        {tr("notify")}
      </Alert>

      {cancel.isError && <Alert className="mt-3 w-full text-start">{tr("cancelError", { error: cancel.error.message })}</Alert>}

      <div className="mt-6 flex w-full flex-col gap-2.5 sm:flex-row">
        <ButtonLink href="/dashboard" size="md" className="flex-1">
          {tr("toDashboard")}
        </ButtonLink>
        {!me.data?.is_demo && (
          <ButtonLink href={`/premium/checkout?plan=${r.plan}`} variant="outline" size="md" className="flex-1">
            {tr("change")}
          </ButtonLink>
        )}
      </div>
      {!me.data?.is_demo &&
        (confirming ? (
          <div className="mt-4 flex flex-wrap items-center justify-center gap-3 text-sm">
            <span className="text-body">{tr("confirmCancel")}</span>
            <Button variant="ghost" size="sm" className="text-danger" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
              {cancel.isPending && <Spinner />}
              {tr("yesCancel")}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>
              {tr("keep")}
            </Button>
          </div>
        ) : (
          <button type="button" onClick={() => setConfirming(true)} className="mt-4 text-sm font-medium text-muted underline hover:text-ink">
            {tr("cancel")}
          </button>
        ))}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4 py-2.5">
      <dt className="text-muted">{k}</dt>
      <dd className="text-end font-medium text-ink">{v}</dd>
    </div>
  );
}
