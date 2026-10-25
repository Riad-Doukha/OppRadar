"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button, ButtonLink, Spinner } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { SectionLabel } from "@/components/ui/inputs";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { intlLocale, type Locale } from "@/i18n/config";
import { ApiError, api, type Me } from "@/lib/api/client";
import { STATUS, useApplications, useSaveApplication, type Application } from "@/lib/applications";
import { labelOf, useOptions } from "@/lib/onboarding/options";
import { useOpportunityText, type MyOpportunity } from "@/lib/opportunities";
import { cn } from "@/lib/utils";

const STEPS = ["answers", "official", "record"] as const;

/**
 * Apply assistant (Figma flow: review answers → captcha → submit). The agent
 * that fills organizer forms isn't shipped; today it prepares your answers to
 * copy, sends you to the official form, and records the application.
 */
export function ApplyPage({ id }: { id: string }) {
  const t = useTranslations("apply");
  const opp = useQuery({ queryKey: ["opportunity", id], queryFn: () => api<MyOpportunity>(`/me/opportunities/${id}`) });
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  const apps = useApplications();
  const existing = apps.data?.find((a) => a.opportunity_id === id);
  const [recorded, setRecorded] = useState<Application | null>(null);

  if (opp.isError) {
    const missing = opp.error instanceof ApiError && opp.error.status === 404;
    return <Alert>{missing ? t("missing") : t("loadError", { error: opp.error.message })}</Alert>;
  }
  if (!opp.data || !me.data) {
    return (
      <Loading label={t("loading")} className="mx-auto max-w-[1032px]">
        <Skeleton className="mx-auto h-9 w-96 max-w-full rounded-full" />
        <div className="grid gap-5 pt-6 lg:grid-cols-[1fr_320px]">
          <Skeleton className="h-[480px] rounded-card" />
          <Skeleton className="h-[320px] rounded-card" />
        </div>
      </Loading>
    );
  }

  const o = opp.data;
  const done = recorded ?? (existing && existing.status !== "draft" ? existing : null);
  const step = done ? 2 : 0;

  return (
    <div className="mx-auto max-w-[1032px]">
      <p className="text-[13px] text-muted">
        {t("crumb")} · <span className="font-bold text-ink">{o.title}</span>
      </p>
      <Stepper current={step} />

      {done ? (
        <Recorded o={o} app={done} />
      ) : (
        <div className="grid gap-5 pt-6 lg:grid-cols-[1fr_320px]">
          <Answers me={me.data} />
          <Submit o={o} readOnly={me.data.is_demo} onRecorded={setRecorded} />
        </div>
      )}
    </div>
  );
}

function Stepper({ current }: { current: number }) {
  const t = useTranslations("apply.steps");
  return (
    <ol className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2 pt-4" aria-label={t("label")}>
      {STEPS.map((key, i) => (
        <li key={key} className="flex items-center gap-2.5" aria-current={i === current ? "step" : undefined}>
          {i > 0 && <span className="hidden h-px w-10 bg-line sm:block" aria-hidden />}
          <span
            className={cn(
              "flex size-7 items-center justify-center rounded-full border text-xs font-bold",
              i < current || current === 2 ? "border-brand bg-brand text-white" : i === current ? "border-ink bg-signal text-on-signal" : "border-line text-muted",
            )}
          >
            {i < current || current === 2 ? "✓" : i + 1}
          </span>
          <span className={cn("text-[13px]", i === current ? "font-bold text-ink" : "text-muted")}>{t(key)}</span>
        </li>
      ))}
    </ol>
  );
}

/** Profile answers most forms ask for, ready to copy. */
function Answers({ me }: { me: Me }) {
  const t = useTranslations("apply");
  const o = useOptions();
  const link = (kind: string) => me.links.find((l) => l.kind === kind)?.url;
  // Labels and known values (levels, countries…) follow the interface language; free text is copied as typed.
  const rows: [string, string | null | undefined][] = [
    [t("fields.fullName"), me.full_name],
    [t("fields.email"), me.email],
    [t("fields.birthYear"), me.birth_year?.toString()],
    [t("fields.nationality"), o.nationalityLabel(me.nationality)],
    [t("fields.location"), [o.wilayaLabel(me.wilaya), o.countryLabel(me.country)].filter(Boolean).join(", ")],
    [t("fields.university"), me.institution],
    [t("fields.level"), labelOf(o.EDUCATION_LEVELS, me.education_level)],
    [t("fields.field"), me.field_of_study],
    [t("fields.currentYear"), me.current_year ? labelOf(o.CURRENT_YEARS, me.current_year) : null],
    [t("fields.graduationYear"), me.graduation_year?.toString()],
    [t("fields.languages"), me.languages.map((l) => `${l.language} (${labelOf(o.LANGUAGE_LEVELS, l.level)})`).join(", ")],
    [t("fields.skills"), me.skills.map((s) => s.name).join(", ")],
    [t("fields.linkedin"), link("linkedin")],
    [t("fields.github"), link("github")],
    [t("fields.portfolio"), link("portfolio")],
    [t("fields.goal"), me.goal],
  ];
  const filled = rows.filter(([, v]) => v);

  return (
    <section className="rounded-card border border-line bg-surface p-5 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="font-display text-xl font-bold text-ink">{t("answersTitle")}</h1>
        <span className="rounded-full bg-brand-soft px-3 py-1 font-mono text-xs font-semibold text-brand-strong">{t("fromProfileCount", { count: filled.length })}</span>
      </div>
      <p className="pt-1 text-[13px] text-muted">
        {t("answersHint")}
      </p>
      <dl className="flex flex-col gap-3 pt-5">
        {filled.map(([label, value]) => (
          <CopyRow key={label} label={label} value={value!} />
        ))}
      </dl>
      {filled.length < rows.length && (
        <p className="pt-4 text-xs text-muted">
          {t.rich("someEmpty", {
            link: (c) => (
              <Link href="/profile" className="font-bold text-brand">
                {c}
              </Link>
            ),
          })}
        </p>
      )}
    </section>
  );
}

function CopyRow({ label, value }: { label: string; value: string }) {
  const t = useTranslations("apply");
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked: the text is selectable anyway */
    }
  }
  return (
    <div>
      <div className="flex items-center justify-between gap-2 pb-1.5">
        <dt className="text-[13px] font-bold text-ink">{label}</dt>
        <span className="flex items-center gap-1 rounded-full bg-brand-soft px-2 py-0.5 text-[11px] font-bold text-brand-strong">
          <span className="size-1.5 rounded-full bg-brand" aria-hidden /> {t("fromProfile")}
        </span>
      </div>
      <dd className="flex items-start gap-2 rounded-field border border-line bg-surface px-3.5 py-2.5">
        <span className="min-w-0 flex-1 text-[15px] break-words text-ink select-all">{value}</span>
        <button type="button" onClick={copy} className="shrink-0 text-xs font-bold text-brand hover:text-brand-strong" aria-label={t("copyLabel", { label })}>
          {copied ? t("copied") : t("copy")}
        </button>
      </dd>
    </div>
  );
}

function Submit({ o, readOnly, onRecorded }: { o: MyOpportunity; readOnly: boolean; onRecorded: (a: Application) => void }) {
  const t = useTranslations("apply");
  const { deadlineText } = useOpportunityText();
  const save = useSaveApplication();
  const [opened, setOpened] = useState(false);
  const [reference, setReference] = useState("");
  const deadline = deadlineText(o.deadline);

  async function record(e: FormEvent) {
    e.preventDefault();
    const app = await save.mutateAsync({ opportunityId: o.id, body: { status: "submitted", ...(reference.trim() && { reference: reference.trim() }) } });
    onRecorded(app);
  }

  return (
    <aside className="flex flex-col gap-3 self-start rounded-card border border-line bg-surface p-5 shadow-card lg:sticky lg:top-24">
      <SectionLabel>{t("applyingTo")}</SectionLabel>
      <div>
        <p className="text-lg font-bold text-ink">{o.title}</p>
        <p className="text-[13px] text-muted">
          {o.organizer} · <span className={deadline.urgent ? "font-bold text-warning" : ""}>{deadline.text}</span>
        </p>
      </div>
      {o.url ? (
        <a
          href={o.url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => setOpened(true)}
          className="flex h-12 items-center justify-center rounded-field bg-brand px-4 text-[15px] font-bold text-white hover:bg-brand-strong"
        >
          {t("openForm")} <span className="inline-block rtl:-scale-x-100">↗</span>
        </a>
      ) : (
        <p className="text-sm text-muted">{t("noLink")}</p>
      )}
      <p className="flex items-center justify-center gap-1.5 rounded-field bg-page px-3 py-2 text-center text-xs font-bold text-body">
        <Image src="/icons/lock-dark.svg" alt="" width={12} height={12} className="icon-adapt" />
        {t("neverSubmits")}
      </p>

      {!readOnly && (
        <form onSubmit={record} className={cn("mt-1 flex flex-col gap-2.5 border-t border-line pt-4", !opened && "opacity-90")}>
          <p className="text-sm font-bold text-ink">{t("doneQuestion")}</p>
          <Input value={reference} onChange={(e) => setReference(e.target.value)} maxLength={120} placeholder={t("referencePlaceholder")} aria-label={t("referenceLabel")} />
          <Button type="submit" variant="outline" size="md" disabled={save.isPending}>
            {save.isPending && <Spinner />} {t("submitted")}
          </Button>
          {save.isError && <p className="text-xs text-danger">{t("recordError", { error: save.error.message })}</p>}
          <p className="text-xs text-muted">{t("trackHint")}</p>
        </form>
      )}
      <Link href={`/opportunities/${o.id}`} className="pt-1 text-center text-[13px] font-bold text-body hover:text-ink">
        <span className="inline-block rtl:-scale-x-100">‹</span> {t("backToOpportunity")}
      </Link>
    </aside>
  );
}

function Recorded({ o, app }: { o: MyOpportunity; app: Application }) {
  const t = useTranslations("apply");
  const ts = useTranslations("applications.status");
  const locale = intlLocale(useLocale() as Locale);
  const status = STATUS[app.status];
  return (
    <section className="mx-auto mt-6 max-w-[540px] rounded-card border border-line bg-surface p-6 text-center shadow-card sm:p-9">
      <div className="mx-auto flex size-16 items-center justify-center rounded-full bg-success-tint">
        <Image src="/icons/check-green.svg" alt="" width={30} height={30} />
      </div>
      <h1 className="pt-4 font-display text-2xl font-bold text-ink">{t("recordedTitle")}</h1>
      <p className="pt-2 text-[15px] text-body">
        {t.rich("recordedBody", { title: o.title, strong: (c) => <strong className="text-ink">{c}</strong> })}
      </p>
      <dl className="mt-5 grid grid-cols-2 gap-4 rounded-field border border-line bg-page/60 p-4 text-start">
        <div>
          <dt className="text-[11px] font-bold tracking-[0.8px] text-muted uppercase">{t("reference")}</dt>
          <dd className="pt-0.5 font-mono text-sm font-bold text-ink">{app.reference || "—"}</dd>
        </div>
        <div>
          <dt className="text-[11px] font-bold tracking-[0.8px] text-muted uppercase">{t("recorded")}</dt>
          <dd className="pt-0.5 text-sm font-bold text-ink">
            {app.submitted_at ? new Date(app.submitted_at).toLocaleString(locale, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] font-bold tracking-[0.8px] text-muted uppercase">{t("submittedOn")}</dt>
          <dd className="pt-0.5 text-sm font-bold text-ink">{t("officialSite")}</dd>
        </div>
        <div>
          <dt className="text-[11px] font-bold tracking-[0.8px] text-muted uppercase">{t("status")}</dt>
          <dd className="pt-1">
            <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-bold", status.tone)}>{ts(app.status)}</span>
          </dd>
        </div>
      </dl>
      <div className="flex flex-wrap justify-center gap-2.5 pt-6">
        <ButtonLink href="/applications" size="md">
          {t("toApplications")} <span className="inline-block rtl:-scale-x-100">→</span>
        </ButtonLink>
        {o.url && (
          <a href={o.url} target="_blank" rel="noopener noreferrer" className="flex h-12 items-center px-3 text-[15px] font-bold text-body hover:text-ink">
            {t("openOfficial")} <span className="inline-block rtl:-scale-x-100">↗</span>
          </a>
        )}
      </div>
    </section>
  );
}
