"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Select } from "@/components/ui/inputs";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { STATUS, useApplications, useRemoveApplication, useSaveApplication, type Application, type ApplicationStatus } from "@/lib/applications";
import { intlLocale, type Locale } from "@/i18n/config";
import { useOptions } from "@/lib/onboarding/options";
import { cn } from "@/lib/utils";

/** Tracked applications with editable status — used on /applications and the dashboard tab. */
export function ApplicationList({ readOnly }: { readOnly: boolean }) {
  const t = useTranslations("applications");
  const apps = useApplications();

  if (apps.isError) return <Alert>{t("loadError", { error: apps.error.message })}</Alert>;
  if (apps.isPending)
    return (
      <Loading label={t("loading")} className="flex flex-col gap-3">
        {[0, 1].map((i) => <Skeleton key={i} className="h-[104px] rounded-card" />)}
      </Loading>
    );
  if (!apps.data.length)
    return (
      <div className="rounded-card border border-dashed border-line bg-surface px-6 py-10 text-center">
        <p className="text-base font-bold text-ink">{t("emptyTitle")}</p>
        <p className="mx-auto max-w-md pt-1.5 text-sm text-muted">
          {t.rich("empty", { strong: (c) => <strong>{c}</strong> })}
        </p>
      </div>
    );

  return (
    <ul className="flex flex-col gap-3">
      {apps.data.map((a) => (
        <Row key={a.id} a={a} readOnly={readOnly} />
      ))}
    </ul>
  );
}

function Row({ a, readOnly }: { a: Application; readOnly: boolean }) {
  const t = useTranslations("applications");
  const locale = intlLocale(useLocale() as Locale);
  const { typeLabel } = useOptions();
  const save = useSaveApplication();
  const remove = useRemoveApplication();
  const [reference, setReference] = useState(a.reference ?? "");
  const o = a.opportunity;
  const status = STATUS[a.status];

  return (
    <li className="rounded-card border border-line bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            {o && <span className="rounded-full bg-brand-soft px-3 py-0.5 text-xs font-bold text-brand-strong">{typeLabel(o.type)}</span>}
            <span className={cn("rounded-full px-3 py-0.5 text-xs font-bold", status.tone)}>{t(`status.${a.status}`)}</span>
          </div>
          <p className="pt-2 text-[17px] font-bold text-ink">
            {o ? (
              <Link href={`/opportunities/${o.id}`} className="hover:text-brand-strong">
                {o.title}
              </Link>
            ) : (
              t("removed")
            )}
          </p>
          <p className="text-[13px] text-muted">
            {[o?.organizer, a.submitted_at && t("submittedOn", { date: new Date(a.submitted_at).toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" }) })].filter(Boolean).join(" · ")}
          </p>
        </div>
        {!readOnly && (
          <div className="flex flex-wrap items-center gap-2">
            <Select
              aria-label={t("statusLabel")}
              value={a.status}
              disabled={save.isPending}
              onChange={(e) => save.mutate({ opportunityId: a.opportunity_id, body: { status: e.target.value as ApplicationStatus } })}
              className="h-10 w-auto min-w-40 text-sm"
            >
              {(Object.keys(STATUS) as ApplicationStatus[]).map((s) => (
                <option key={s} value={s}>
                  {t(`status.${s}`)}
                </option>
              ))}
            </Select>
            <button
              type="button"
              onClick={() => window.confirm(t("confirmRemove")) && remove.mutate(a.opportunity_id)}
              className="px-2 text-[13px] font-bold text-muted hover:text-danger"
            >
              {t("remove")}
            </button>
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2 pt-3">
        <label className="text-xs font-bold text-muted" htmlFor={`ref-${a.id}`}>
          {t("reference")}
        </label>
        <input
          id={`ref-${a.id}`}
          value={reference}
          readOnly={readOnly}
          maxLength={120}
          onChange={(e) => setReference(e.target.value)}
          onBlur={() => reference !== (a.reference ?? "") && save.mutate({ opportunityId: a.opportunity_id, body: { reference: reference.trim() || null } })}
          placeholder="—"
          className="h-8 min-w-0 flex-1 rounded-lg border border-line bg-page/60 px-2.5 font-mono text-sm text-ink outline-none focus:border-brand sm:max-w-64"
        />
        {o?.url && (
          <a href={o.url} target="_blank" rel="noopener noreferrer" className="ms-auto text-[13px] font-bold text-body hover:text-ink">
            {t("official")} <span className="inline-block rtl:-scale-x-100">↗</span>
          </a>
        )}
      </div>
      {(save.isError || remove.isError) && <p className="pt-2 text-xs text-danger">{t("updateFailed")}</p>}
    </li>
  );
}
