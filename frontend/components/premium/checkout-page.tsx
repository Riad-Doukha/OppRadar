"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button, Spinner } from "@/components/ui/button";
import { SectionLabel, Segmented } from "@/components/ui/inputs";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Me } from "@/lib/api/client";
import { PAYMENT_METHODS, PLAN_FEATURES, PRICES, useDzd, usePremium, useReserve, type Billing, type PaymentMethod, type Plan } from "@/lib/premium";
import { cn } from "@/lib/utils";

import { ComingSoonNotice, PreviewPill } from "./coming-soon";

/**
 * Figma "checkout", turned into an early-access reservation: the user picks the
 * plan, billing and the payment method they'd use. No card details are asked
 * and nothing is charged — payments aren't live.
 */
export function CheckoutPage() {
  const t = useTranslations("premium");
  const dzd = useDzd();
  const router = useRouter();
  const params = useSearchParams();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  const premium = usePremium();
  const reserve = useReserve();

  const [plan, setPlan] = useState<Plan>(params.get("plan") === "clubs" ? "clubs" : "premium");
  const [billing, setBilling] = useState<Billing>("monthly");
  const [method, setMethod] = useState<PaymentMethod | null>(null);

  // Editing an existing reservation starts from what was saved.
  const saved = premium.data?.reservation;
  useEffect(() => {
    if (!saved) return;
    if (!params.get("plan")) setPlan(saved.plan);
    setBilling(saved.billing);
    setMethod(saved.payment_method ?? null);
  }, [saved, params]);

  const readOnly = me.data?.is_demo ?? false;
  const price = PRICES[plan][billing];
  const plans: { value: Plan; label: string }[] = [
    { value: "premium", label: t("checkout.premium") },
    { value: "clubs", label: t("checkout.clubs") },
  ];
  const billings: { value: Billing; label: string }[] = [
    { value: "monthly", label: t("checkout.monthly") },
    { value: "yearly", label: t("checkout.yearly") },
  ];

  function submit(e: FormEvent) {
    e.preventDefault();
    reserve.mutate({ plan, billing, payment_method: method }, { onSuccess: () => router.push("/premium/reserved") });
  }

  return (
    <div className="mx-auto max-w-[960px]">
      <Link href="/premium" className="text-sm font-bold text-brand hover:underline">
        <span className="inline-block rtl:-scale-x-100">←</span> {t("checkout.back")}
      </Link>
      <div className="flex flex-wrap items-center gap-3 pt-3">
        <h1 className="font-display text-2xl font-bold text-ink sm:text-[32px]">{saved ? t("checkout.titleChange") : t("checkout.titleNew")}</h1>
        <PreviewPill>{t("checkout.pill")}</PreviewPill>
      </div>
      <ComingSoonNotice className="mt-4" />

      {premium.isPending ? (
        <Skeleton className="mt-6 h-[420px] w-full rounded-card" />
      ) : (
        <form onSubmit={submit} className="grid gap-5 pt-6 lg:grid-cols-[1fr_340px]">
          <div className="flex flex-col gap-5 rounded-card border border-line bg-surface p-5 sm:p-7">
            <fieldset className="flex flex-col gap-2.5">
              <legend className="contents">
                <SectionLabel>{t("checkout.plan")}</SectionLabel>
              </legend>
              <Segmented label={t("checkout.plan")} value={plan} options={plans} onChange={setPlan} />
            </fieldset>
            <fieldset className="flex flex-col gap-2.5">
              <legend className="contents">
                <SectionLabel>{t("checkout.billing")}</SectionLabel>
              </legend>
              <Segmented label={t("checkout.billing")} value={billing} options={billings} onChange={setBilling} />
            </fieldset>

            <fieldset className="flex flex-col gap-2.5">
              <legend className="contents">
                <SectionLabel>{t("checkout.pay")}</SectionLabel>
              </legend>
              <p className="text-[13px] text-body">{t("checkout.payHint")}</p>
              <div role="radiogroup" aria-label={t("checkout.payLabel")} className="grid gap-2.5 sm:grid-cols-2">
                {PAYMENT_METHODS.map((m) => {
                  const checked = method === m;
                  return (
                    <label
                      key={m}
                      className={cn("flex cursor-pointer items-start gap-2.5 rounded-field border p-3.5 transition-colors", checked ? "border-brand bg-page" : "border-line bg-surface hover:border-faint")}
                    >
                      <input
                        type="radio"
                        name="method"
                        value={m}
                        checked={checked}
                        onChange={() => setMethod(m)}
                        onClick={() => checked && setMethod(null)}
                        className="mt-0.5 accent-[var(--color-brand)]"
                      />
                      <span>
                        <span className="block text-sm font-bold text-ink">{t(`methods.${m}`)}</span>
                        <span className="block text-xs text-muted">{t(`methods.${m}_hint`)}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
            </fieldset>
          </div>

          <aside className="flex h-fit flex-col gap-4 rounded-card border border-line bg-surface p-5 shadow-card sm:p-6">
            <SectionLabel>{t("checkout.summary")}</SectionLabel>
            <div>
              <p className="text-lg font-bold text-ink">{t(`plans.${plan}`)}</p>
              <p className="text-sm text-body">{t("checkout.planned", { price: dzd(price), period: t(billing === "yearly" ? "checkout.year" : "checkout.month") })}</p>
            </div>
            <ul className="flex flex-col gap-1.5 text-[13px] text-body">
              {PLAN_FEATURES[plan].slice(0, 4).map((f) => (
                <li key={f}>
                  ○ {t(`features.${plan}.${f}` as Parameters<typeof t>[0])} <span className="text-muted">{t("checkout.soon")}</span>
                </li>
              ))}
            </ul>
            <div className="flex items-baseline justify-between border-t border-line pt-4">
              <span className="text-sm font-bold text-ink">{t("checkout.total")}</span>
              <span className="font-display text-2xl font-bold text-ink">{dzd(0)}</span>
            </div>
            <p className="-mt-2 text-xs text-muted">{t("checkout.totalHint")}</p>

            {reserve.isError && <Alert>{t("checkout.error", { error: reserve.error.message })}</Alert>}
            {readOnly && <Alert tone="info">{t("checkout.demo")}</Alert>}
            <Button type="submit" size="md" block disabled={readOnly || reserve.isPending}>
              {reserve.isPending && <Spinner />}
              {saved ? t("checkout.save") : plan === "clubs" ? t("checkout.joinFree") : t("checkout.reserveFree")}
            </Button>
          </aside>
        </form>
      )}
    </div>
  );
}
