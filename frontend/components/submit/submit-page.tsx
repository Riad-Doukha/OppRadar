"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { OpportunityForm } from "@/components/opportunity-form/opportunity-form";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { SectionLabel } from "@/components/ui/inputs";
import { Skeleton } from "@/components/ui/skeleton";
import { intlLocale, type Locale } from "@/i18n/config";
import { api, type Me } from "@/lib/api/client";
import { REVIEW_TONE, useMySubmissions, useSubmit, type SubmissionIn } from "@/lib/review";
import { cn } from "@/lib/utils";

/** Organisations propose an opportunity; it goes public after an admin review. */
export function SubmitPage() {
  const t = useTranslations("submit");
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  const submit = useSubmit();
  const [formKey, setFormKey] = useState(0);
  const readOnly = me.data?.is_demo ?? false;

  return (
    <div className="mx-auto grid max-w-[1112px] gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0">
        <h1 className="font-display text-2xl font-bold tracking-[-0.5px] text-ink sm:text-[28px]">{t("title")}</h1>
        <p className="max-w-2xl pt-1 text-sm text-body">{t("subtitle")}</p>
        <p className="pt-2 text-xs font-bold text-muted">{t("rules")}</p>

        {readOnly && (
          <Alert tone="info" className="mt-4">
            {t("demo")}
          </Alert>
        )}

        <section className="mt-5 rounded-card border border-line bg-surface p-5 sm:p-7">
          {submit.isSuccess ? (
            <div className="flex flex-col items-start gap-4">
              <Alert tone="info">{t("sent")}</Alert>
              <Button
                variant="outline"
                size="md"
                onClick={() => {
                  submit.reset();
                  setFormKey((k) => k + 1);
                }}
              >
                {t("another")}
              </Button>
            </div>
          ) : (
            <OpportunityForm
              key={formKey}
              variant="submit"
              submitLabel={submit.isPending ? t("sending") : t("send")}
              busy={submit.isPending}
              disabled={readOnly}
              error={submit.isError ? t("error", { error: submit.error.message }) : null}
              onSubmit={(values) => submit.mutate(values as SubmissionIn)}
            />
          )}
        </section>
      </div>

      <MySubmissions />
    </div>
  );
}

function MySubmissions() {
  const t = useTranslations("submit");
  const locale = intlLocale(useLocale() as Locale);
  const list = useMySubmissions();

  return (
    <aside className="flex flex-col gap-3 self-start rounded-card border border-line bg-surface p-5 lg:sticky lg:top-24">
      <SectionLabel>{t("mine")}</SectionLabel>
      {list.isPending && <Skeleton className="h-20 w-full rounded-field" />}
      {list.isError && <Alert>{t("loadError", { error: list.error.message })}</Alert>}
      {list.data?.length === 0 && <p className="text-sm text-muted">{t("mineEmpty")}</p>}
      <ul className="flex flex-col gap-2.5">
        {list.data?.map((s) => (
          <li key={s.id} className="rounded-field border border-line px-3.5 py-3">
            <div className="flex items-start justify-between gap-2">
              <p className="min-w-0 text-sm font-bold break-words text-ink">{s.title}</p>
              <span className={cn("shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-bold", REVIEW_TONE[s.review_status])}>{t(`status.${s.review_status}`)}</span>
            </div>
            <p className="pt-0.5 text-xs text-muted">
              {s.created_at && t("submittedOn", { date: new Date(s.created_at).toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" }) })}
            </p>
            {s.review_note && <p className="pt-1.5 text-xs text-body">{t("adminNote", { note: s.review_note })}</p>}
            {s.review_status === "approved" && (
              <Link href={`/opportunities/${s.id}`} className="mt-1.5 inline-block text-xs font-bold text-brand">
                {t("view")} <span className="inline-block rtl:-scale-x-100">→</span>
              </Link>
            )}
          </li>
        ))}
      </ul>
    </aside>
  );
}
