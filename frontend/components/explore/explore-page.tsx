"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button, ButtonLink, Spinner } from "@/components/ui/button";
import { Pill, Select } from "@/components/ui/inputs";
import { Loading, OpportunityCardSkeleton } from "@/components/ui/skeleton";
import { api, type Schemas } from "@/lib/api/client";
import type { OpportunityType } from "@/lib/onboarding/options";
import { metaLine, useOpportunityText } from "@/lib/opportunities";
import { cn } from "@/lib/utils";

type Opportunity = Schemas["OpportunityOut"];
type Page = Schemas["OpportunityPage"];

const PAGE = 12;
const TYPES: OpportunityType[] = ["hackathon", "datathon", "competition", "scholarship", "internship", "fellowship", "bootcamp", "volunteer", "course", "job"];
const MODES = ["onsite", "hybrid", "remote"] as const;

/** Public browse/search (no account needed). Filters live in the URL (?q=&type=&mode=). */
export function ExplorePage() {
  const t = useTranslations("explore");
  const to = useTranslations("opportunity");
  const { typeLabel } = useOpportunityText();
  const router = useRouter();
  const params = useSearchParams();
  const q = params.get("q") ?? "";
  const type = params.get("type") as OpportunityType | null;
  const mode = params.get("mode");
  const [draft, setDraft] = useState(q);

  const go = (next: Record<string, string | null>) => {
    const sp = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v) sp.set(k, v);
      else sp.delete(k);
    }
    router.replace(`/explore${sp.size ? `?${sp}` : ""}`, { scroll: false });
  };

  const feed = useInfiniteQuery({
    queryKey: ["explore", q, type, mode],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => {
      const sp = new URLSearchParams({ limit: String(PAGE), offset: String(pageParam) });
      if (q) sp.set("q", q);
      if (type) sp.set("type", type);
      if (mode) sp.set("mode", mode);
      return api<Page>(`/opportunities?${sp}`);
    },
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined),
  });
  const items = useMemo(() => feed.data?.pages.flatMap((p) => p.items) ?? [], [feed.data]);
  const total = feed.data?.pages[0]?.total ?? 0;

  function search(e: FormEvent) {
    e.preventDefault();
    go({ q: draft.trim() || null });
  }

  return (
    <main className="mx-auto max-w-[1112px] px-4 pt-8 pb-16 md:px-8">
      <h1 className="font-display text-[28px] font-bold tracking-[-0.5px] text-ink md:text-[34px]">{t("title")}</h1>
      <p className="max-w-2xl pt-1.5 text-[15px] text-body">{t("subtitle")}</p>

      <form onSubmit={search} role="search" className="mt-5 flex max-w-2xl items-center gap-2.5 rounded-card border border-line bg-surface px-3 py-2.5 focus-within:shadow-focus">
        <Image src="/icons/search.svg" alt="" width={16} height={16} />
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={t("search")}
          aria-label={t("search")}
          maxLength={200}
          className="min-w-0 flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-faint"
        />
        <Button type="submit" size="sm">
          {t("searchButton")}
        </Button>
      </form>

      <div className="flex flex-wrap items-center gap-2 pt-4">
        <Chip active={!type} onClick={() => go({ type: null })}>
          {t("allTypes")}
        </Chip>
        {TYPES.map((ty) => (
          <Chip key={ty} active={type === ty} onClick={() => go({ type: type === ty ? null : ty })}>
            {typeLabel(ty)}
          </Chip>
        ))}
        <Select aria-label={t("anyFormat")} value={mode ?? ""} onChange={(e) => go({ mode: e.target.value || null })} className="h-8 w-auto min-w-36 rounded-full py-0 text-[13px]">
          <option value="">{t("anyFormat")}</option>
          {MODES.map((m) => (
            <option key={m} value={m}>
              {to(`mode.${m}`)}
            </option>
          ))}
        </Select>
      </div>

      <p className="pt-5 text-sm text-muted" aria-live="polite">
        {feed.isSuccess && (
          <>
            {t("results", { count: total })} {q && t("for", { q })}{" "}
            {(q || type || mode) && (
              <button
                type="button"
                className="font-bold text-brand"
                onClick={() => {
                  setDraft("");
                  router.replace("/explore", { scroll: false });
                }}
              >
                {t("clear")}
              </button>
            )}
          </>
        )}
      </p>

      <div className="grid gap-4 pt-3 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="flex min-w-0 flex-col gap-4">
          {feed.isPending && (
            <Loading label={t("loading")} className="flex flex-col gap-4">
              <OpportunityCardSkeleton />
              <OpportunityCardSkeleton />
            </Loading>
          )}
          {feed.isError && <Alert>{t("loadError", { error: feed.error.message })}</Alert>}
          {feed.isSuccess && items.length === 0 && <p className="rounded-card border border-dashed border-line bg-surface px-6 py-10 text-center text-sm text-muted">{t("empty")}</p>}
          {items.map((o) => (
            <Card key={o.id} o={o} />
          ))}
          {feed.hasNextPage && (
            <Button variant="outline" size="md" className="self-center" onClick={() => feed.fetchNextPage()} disabled={feed.isFetchingNextPage}>
              {feed.isFetchingNextPage && <Spinner />}
              {t("more", { left: total - items.length })}
            </Button>
          )}
        </div>
        <aside className="flex h-fit flex-col gap-3 rounded-card bg-night p-5 text-white lg:sticky lg:top-24">
          <p className="font-display text-lg font-bold">{t("cta")}</p>
          <p className="text-sm text-on-night">{t("ctaBody")}</p>
          <ButtonLink href="/signup" size="md" className="bg-signal text-on-signal hover:bg-signal-hover">
            {t("cta")}
          </ButtonLink>
        </aside>
      </div>
    </main>
  );
}

function Card({ o }: { o: Opportunity }) {
  const t = useTranslations("explore");
  const to = useTranslations("opportunity");
  const { typeLabel, deadlineText, modeLabel } = useOpportunityText();
  const deadline = deadlineText(o.deadline);
  const flagged = o.trust_level === "suspicious" || o.trust_level === "scam";
  const mode = modeLabel(o.mode);
  return (
    <article className="rounded-card border border-line bg-surface p-[22px] shadow-[0_1px_1.5px_rgb(30_17_62/0.05)]">
      <div className="flex flex-wrap items-center gap-2">
        <Pill className="h-7 text-xs">{typeLabel(o.type)}</Pill>
        {o.trust_level === "verified" && <span className="rounded-full bg-success-tint px-3 py-1 text-xs font-bold text-success">{to("trust.verified")}</span>}
        {flagged && <span className="rounded-full bg-danger-soft px-3 py-1 text-xs font-bold text-danger">{o.trust_level === "scam" ? to("trust.likelyScam") : to("trust.check")}</span>}
      </div>
      <h2 className="pt-2.5 text-lg leading-snug font-bold text-ink">
        {/* The detail page needs an account: logging in brings the visitor back here. */}
        <Link href={`/opportunities/${o.id}`} className="hover:text-brand-strong">
          {o.title}
        </Link>
      </h2>
      <p className="pt-1 text-[13px] text-muted">{metaLine(o)}</p>
      {o.summary && <p className="line-clamp-2 pt-2 text-sm text-body">{o.summary}</p>}
      <div className="flex flex-wrap items-center gap-2 pt-3.5">
        <span className={cn("text-[13px] font-bold", deadline.urgent ? "text-warning" : "text-ink")}>{deadline.text}</span>
        {mode && <Pill muted className="h-[26px] text-xs">{mode}</Pill>}
      </div>
      <div className="mt-4 flex flex-wrap justify-end gap-2.5 border-t border-line pt-4">
        {o.url && (
          <a href={o.url} target="_blank" rel="noopener noreferrer" className="flex h-10 items-center px-3 text-sm font-bold text-body hover:text-ink">
            {t("official")} <span className="ms-1 inline-block rtl:-scale-x-100">↗</span>
          </a>
        )}
        <ButtonLink href={`/opportunities/${o.id}`} className="h-10 text-sm">
          {t("details")}
        </ButtonLink>
      </div>
    </article>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn("flex h-8 items-center rounded-full border px-3.5 text-[13px]", active ? "border-transparent bg-brand-soft font-bold text-brand-strong" : "border-line bg-surface font-medium text-body hover:border-faint")}
    >
      {children}
    </button>
  );
}
