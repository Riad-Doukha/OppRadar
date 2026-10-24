"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { OpportunityForm, type OpportunityValues } from "@/components/opportunity-form/opportunity-form";
import { Alert } from "@/components/ui/alert";
import { Button, Spinner } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { Pill, Select } from "@/components/ui/inputs";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { intlLocale, type Locale } from "@/i18n/config";
import { api, type Me } from "@/lib/api/client";
import { useOpportunityText } from "@/lib/opportunities";
import {
  REVIEW_TONE,
  TRUST_LEVELS,
  TRUST_TONE,
  useAdminList,
  useAdminStats,
  useCreateOpportunity,
  useDeleteOpportunity,
  useIngestionRuns,
  useReview,
  useRunIngestion,
  useUpdateOpportunity,
  type AdminOpportunityIn,
  type AdminView,
  type Reviewed,
  type TrustLevel,
} from "@/lib/review";
import { cn } from "@/lib/utils";

const TABS = ["queue", "flagged", "all", "new", "ingest"] as const;
type Tab = (typeof TABS)[number];

/** Admin area: review queue, flagged sources, every opportunity, and "add". */
export function AdminPage() {
  const t = useTranslations("admin");
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });

  if (me.isPending) return <Skeleton className="mx-auto h-64 max-w-[1112px] rounded-card" />;
  if (!me.data?.is_admin) {
    return (
      <div className="mx-auto max-w-xl rounded-card border border-line bg-surface p-8 text-center">
        <p className="text-lg font-bold text-ink">{t("forbidden")}</p>
        <p className="pt-2 text-sm text-muted">{t("forbiddenHint")}</p>
      </div>
    );
  }
  return <Admin />;
}

function Admin() {
  const t = useTranslations("admin");
  const router = useRouter();
  const params = useSearchParams();
  const requested = params.get("tab") as Tab | null;
  const tab: Tab = requested && TABS.includes(requested) ? requested : "queue";
  const stats = useAdminStats();
  const s = stats.data;

  return (
    <div className="mx-auto max-w-[1112px]">
      <h1 className="font-display text-2xl font-bold tracking-[-0.5px] text-ink sm:text-[28px]">{t("title")}</h1>
      <p className="pt-1 text-sm text-body">{t("subtitle")}</p>

      <div className="grid grid-cols-2 gap-3 pt-5 sm:grid-cols-4">
        {(["pending", "flagged", "published", "rejected"] as const).map((k) => (
          <div key={k} className="rounded-card border border-line bg-surface px-[18px] py-3.5">
            <div className={cn("font-mono text-[26px] font-semibold", k === "pending" ? "text-warning" : k === "flagged" ? "text-danger" : "text-ink")}>
              {s ? s[k] : <Skeleton className="h-8 w-8" />}
            </div>
            <p className="text-xs font-bold tracking-[0.8px] text-muted uppercase">{t(`stats.${k}`)}</p>
          </div>
        ))}
      </div>

      <div role="tablist" aria-label={t("tabs.label")} className="mt-5 flex gap-7 overflow-x-auto border-b border-line">
        {TABS.map((key) => (
          <button
            key={key}
            role="tab"
            type="button"
            aria-selected={tab === key}
            onClick={() => router.replace(key === "queue" ? "/admin" : `/admin?tab=${key}`, { scroll: false })}
            className={cn("flex shrink-0 items-center gap-1.5 border-b-[3px] pt-3 pb-3 text-[15px]", tab === key ? "border-brand font-bold text-ink" : "border-transparent font-medium text-muted hover:text-ink")}
          >
            {t(`tabs.${key}`)}
            {key === "queue" && s && s.pending > 0 && <span className="rounded-full bg-warning-tint px-[7px] py-0.5 font-mono text-[11px] font-bold text-warning">{s.pending}</span>}
            {key === "flagged" && s && s.flagged > 0 && <span className="rounded-full bg-danger-soft px-[7px] py-0.5 font-mono text-[11px] font-bold text-danger">{s.flagged}</span>}
          </button>
        ))}
      </div>

      <div className="pt-4">{tab === "new" ? <NewOpportunity /> : tab === "ingest" ? <Ingestion /> : <List key={tab} view={tab} />}</div>
    </div>
  );
}

function List({ view }: { view: AdminView }) {
  const t = useTranslations("admin");
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const list = useAdminList(view, q);
  const items = useMemo(() => list.data?.pages.flatMap((p) => p.items) ?? [], [list.data]);
  const total = list.data?.pages[0]?.total ?? 0;

  return (
    <div className="flex flex-col gap-3">
      <form
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          setQ(draft.trim());
        }}
      >
        <Input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={t("search")} aria-label={t("search")} className="sm:max-w-md" />
      </form>
      {list.isPending && (
        <Loading label={t("loading")} className="flex flex-col gap-3">
          {[0, 1].map((i) => <Skeleton key={i} className="h-32 rounded-card" />)}
        </Loading>
      )}
      {list.isError && <Alert>{t("loadError", { error: list.error.message })}</Alert>}
      {list.isSuccess && items.length === 0 && (
        <p className="rounded-card border border-dashed border-line bg-surface px-6 py-10 text-center text-sm text-muted">{t(`empty.${view}`)}</p>
      )}
      {items.map((o) => (
        <Row key={o.id} o={o} />
      ))}
      {list.hasNextPage && (
        <Button variant="outline" size="md" className="self-center" onClick={() => list.fetchNextPage()} disabled={list.isFetchingNextPage}>
          {list.isFetchingNextPage && <Spinner />}
          {t("more", { left: total - items.length })}
        </Button>
      )}
    </div>
  );
}

function Row({ o }: { o: Reviewed }) {
  const t = useTranslations("admin");
  const to = useTranslations("opportunity");
  const locale = intlLocale(useLocale() as Locale);
  const { typeLabel, deadlineText, scamFlag } = useOpportunityText();
  const review = useReview();
  const update = useUpdateOpportunity();
  const remove = useDeleteOpportunity();
  const [editing, setEditing] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const error = review.error ?? update.error ?? remove.error;
  const busy = review.isPending || update.isPending || remove.isPending;
  const deadline = deadlineText(o.deadline);
  const flags = o.scam_flags.map((f) => scamFlag(String((f as { flag?: string }).flag ?? ""))).filter(Boolean);

  if (editing) {
    return (
      <section className="rounded-card border border-brand bg-surface p-5 sm:p-6">
        <OpportunityForm
          variant="admin"
          initial={o}
          submitLabel={t("save")}
          busy={update.isPending}
          error={update.isError ? t("actionError", { error: update.error.message }) : null}
          onCancel={() => setEditing(false)}
          onSubmit={(values: OpportunityValues) => update.mutate({ id: o.id, body: values }, { onSuccess: () => setEditing(false) })}
        />
      </section>
    );
  }

  return (
    <article className="rounded-card border border-line bg-surface p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Pill className="h-7 text-xs">{typeLabel(o.type)}</Pill>
        <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-bold", REVIEW_TONE[o.review_status])}>{t(`review.${o.review_status}`)}</span>
        <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-bold", TRUST_TONE[o.trust_level])}>{t(`trust.${o.trust_level}`)}</span>
        <span className="text-xs text-muted">· {t(`via.${o.added_via as "form" | "pipeline" | "user"}`)}</span>
      </div>
      <h3 className="pt-2 text-lg leading-snug font-bold text-ink">{o.title}</h3>
      <p className="text-[13px] text-muted">
        {[o.organizer, [o.location, o.country].filter(Boolean).join(", "), o.mode && to(`mode.${o.mode}`), deadline.text].filter(Boolean).join(" · ")}
      </p>
      {o.summary && <p className="line-clamp-3 pt-2 text-sm text-body">{o.summary}</p>}
      {flags.length > 0 && <p className="pt-2 text-xs font-bold text-danger">{t("flags", { flags: flags.join(" · ") })}</p>}
      {o.review_notes.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-2">
          {o.review_notes.map((note) => (
            <span key={note} className="rounded-full bg-warning-tint px-2.5 py-0.5 text-[11px] font-bold text-warning">
              {to("chips.needsReview")}: {note}
            </span>
          ))}
        </div>
      )}
      <p className="flex flex-wrap gap-x-3 gap-y-1 pt-2 text-xs text-muted">
        {o.created_at && <span>{t("created", { date: new Date(o.created_at).toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" }) })}</span>}
        {o.contact_email && <span dir="ltr">{t("contact", { email: o.contact_email })}</span>}
        {o.url && (
          <a href={o.url} target="_blank" rel="noopener noreferrer" className="font-bold text-brand">
            {t("official")} <span className="inline-block rtl:-scale-x-100">↗</span>
          </a>
        )}
        {o.review_status === "approved" && (
          <Link href={`/opportunities/${o.id}`} className="font-bold text-body hover:text-ink">
            /opportunities/{o.id.slice(0, 8)}…
          </Link>
        )}
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4">
        {o.review_status !== "approved" && (
          <Button size="sm" disabled={busy} onClick={() => review.mutate({ id: o.id, body: { status: "approved", note: null, trust_level: null } })}>
            {o.review_status === "pending" ? t("approve") : t("republish")}
          </Button>
        )}
        {o.review_status !== "rejected" && !rejecting && (
          <Button variant="outline" size="sm" disabled={busy} onClick={() => setRejecting(true)}>
            {o.review_status === "pending" ? t("reject") : t("unpublish")}
          </Button>
        )}
        <Select
          aria-label={t("trustLabel")}
          value={o.trust_level}
          disabled={busy}
          onChange={(e) => update.mutate({ id: o.id, body: { trust_level: e.target.value as TrustLevel } })}
          className="h-9 w-auto min-w-44 text-sm"
        >
          {TRUST_LEVELS.map((l) => (
            <option key={l} value={l}>
              {t(`trust.${l}`)}
            </option>
          ))}
        </Select>
        <Button variant="ghost" size="sm" disabled={busy} onClick={() => setEditing(true)}>
          {t("edit")}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="ms-auto text-danger hover:text-danger"
          disabled={busy}
          onClick={() => window.confirm(t("confirmDelete", { title: o.title })) && remove.mutate(o.id)}
        >
          {t("delete")}
        </Button>
        {busy && <Spinner className="text-brand" />}
      </div>

      {rejecting && (
        <form
          className="mt-3 flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            review.mutate({ id: o.id, body: { status: "rejected", note: note.trim() || null, trust_level: null } }, { onSuccess: () => setRejecting(false) });
          }}
        >
          <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} placeholder={t("notePlaceholder")} aria-label={t("notePlaceholder")} />
          <div className="flex gap-2">
            <Button type="submit" size="sm" className="bg-danger hover:bg-danger-strong" disabled={busy}>
              {t("confirmReject")}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setRejecting(false)}>
              {t("cancel")}
            </Button>
          </div>
        </form>
      )}
      {error && <Alert className="mt-3">{t("actionError", { error: error.message })}</Alert>}
    </article>
  );
}

function NewOpportunity() {
  const t = useTranslations("admin");
  const create = useCreateOpportunity();
  const [formKey, setFormKey] = useState(0);
  return (
    <section className="rounded-card border border-line bg-surface p-5 sm:p-7">
      {create.isSuccess && (
        <Alert tone="info" className="mb-4">
          {t("published")}{" "}
          <Link href={`/opportunities/${(create.data as Reviewed).id}`} className="font-bold text-brand underline">
            {t("viewIt")}
          </Link>
        </Alert>
      )}
      <OpportunityForm
        key={formKey}
        variant="admin"
        submitLabel={t("create")}
        busy={create.isPending}
        error={create.isError ? t("actionError", { error: create.error.message }) : null}
        onSubmit={(values) => create.mutate(values as AdminOpportunityIn, { onSuccess: () => setFormKey((k) => k + 1) })}
      />
    </section>
  );
}

function Ingestion() {
  const t = useTranslations("admin.ingest");
  const locale = intlLocale(useLocale() as Locale);
  const runs = useIngestionRuns();
  const run = useRunIngestion();
  const when = (iso: string) => new Date(iso).toLocaleString(locale, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-card border border-line bg-surface p-5 sm:p-6">
        <h2 className="text-lg font-bold text-ink">{t("title")}</h2>
        <p className="max-w-3xl pt-1 text-sm text-body">{t("body")}</p>
        <Button size="md" className="mt-4" disabled={run.isPending} onClick={() => run.mutate()}>
          {run.isPending && <Spinner />}
          {run.isPending ? t("running") : t("run")}
        </Button>
        {run.isError && <Alert className="mt-3">{t("error", { error: run.error.message })}</Alert>}
      </section>

      <section className="rounded-card border border-line bg-surface p-5 sm:p-6">
        <h2 className="text-base font-bold text-ink">{t("runs")}</h2>
        {runs.isPending && <Skeleton className="mt-3 h-16 w-full rounded-field" />}
        {runs.data?.length === 0 && <p className="pt-2 text-sm text-muted">{t("none")}</p>}
        <ul className="mt-2 divide-y divide-line">
          {runs.data?.map((r) => {
            type Usage = { made?: number; limit?: number };
            type Item = { title: string; url?: string; reason?: string; source?: string };
            const rep = r.report as { searches?: Usage; extractions?: Usage; failures?: string[]; rejected?: Item[]; pending_llm?: Item[] };
            return (
              <li key={r.id} className="py-3 text-sm">
                <p className="flex flex-wrap items-center gap-2">
                  <span className="font-bold text-ink">{when(r.started_at)}</span>
                  <span className="rounded-full bg-page px-2.5 py-0.5 text-xs font-bold text-muted">{t(r.trigger)}</span>
                  {r.error && <span className="rounded-full bg-danger-soft px-2.5 py-0.5 text-xs font-bold text-danger">{t("error", { error: r.error })}</span>}
                </p>
                <p className="pt-1 font-mono text-xs text-body">
                  {t("counts", { fetched: r.items_fetched, new: r.items_new, saved: r.items_saved, flagged: r.items_flagged })}
                </p>
                <p className="text-xs text-muted">
                  {t("budget", {
                    searches: rep.searches?.made ?? 0,
                    searchLimit: rep.searches?.limit ?? 0,
                    extractions: rep.extractions?.made ?? 0,
                    extractionLimit: rep.extractions?.limit ?? 0,
                  })}
                </p>
                {(["rejected", "pending_llm"] as const).map((key) => {
                  const items = rep[key] ?? [];
                  return items.length > 0 ? (
                    <details key={key} className="pt-1 text-xs text-body">
                      <summary className="cursor-pointer font-bold">{t(key === "rejected" ? "rejected" : "pendingLlm", { count: items.length })}</summary>
                      <ul className="list-disc ps-5 pt-1">
                        {items.slice(0, 20).map((it, i) => (
                          <li key={i}>
                            {it.url ? (
                              <a href={it.url} target="_blank" rel="noopener noreferrer" className="underline">
                                {it.title}
                              </a>
                            ) : (
                              it.title
                            )}
                            {it.reason && <span className="text-muted"> — {it.reason}</span>}
                          </li>
                        ))}
                      </ul>
                    </details>
                  ) : null;
                })}
                {rep.failures && rep.failures.length > 0 && <p className="pt-1 text-xs text-warning">{t("failures", { list: rep.failures.slice(0, 3).join(" · ") })}</p>}
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
