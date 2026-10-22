"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { initialsOf } from "@/components/app/app-shell";
import { Alert } from "@/components/ui/alert";
import { Button, ButtonLink } from "@/components/ui/button";
import { Pill } from "@/components/ui/inputs";
import { Loading, OpportunityCardSkeleton, Skeleton } from "@/components/ui/skeleton";
import { api, type Me, type Schemas } from "@/lib/api/client";
import { CURRENT_YEARS, EDUCATION_LEVELS, labelOf } from "@/lib/onboarding/options";
import { isComplete } from "@/lib/onboarding/status";
import { TYPE_LABELS, type FeedTab, type OpportunityType } from "@/lib/opportunities";
import { cn } from "@/lib/utils";

import { OpportunityCard } from "./opportunity-card";

type Stats = Schemas["DashboardStats"];
type Page = Schemas["MyOpportunityPage"];
const PAGE = 10;

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export function Dashboard() {
  const router = useRouter();
  const params = useSearchParams();
  const q = params.get("q") ?? "";
  const tab = (params.get("tab") as FeedTab | "applications" | null) ?? "for_you";
  const [type, setType] = useState<OpportunityType | null>(null);

  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  const stats = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Stats>("/me/dashboard") });

  const setTab = (next: string) => {
    const sp = new URLSearchParams(params);
    if (next === "for_you") sp.delete("tab");
    else sp.set("tab", next);
    setType(null);
    router.replace(`/dashboard${sp.size ? `?${sp}` : ""}`, { scroll: false });
  };

  if (me.isError) {
    return <Alert>We couldn&apos;t load your dashboard: {me.error.message}. Is the API running?</Alert>;
  }
  // Render as soon as the profile is here; counts fill in when they arrive.
  if (!me.data) return <DashboardSkeleton />;

  const s = stats.data;
  const firstName = (me.data.full_name || "").split(" ")[0];
  const tabs: { key: FeedTab | "applications"; label: string; count?: number }[] = [
    { key: "for_you", label: "For you", count: s?.for_you },
    { key: "closing", label: "Closing soon", count: s?.closing_this_week },
    { key: "saved", label: "Saved", count: s?.saved },
    { key: "applications", label: "My applications", count: s?.applications },
  ];

  return (
    <div className="mx-auto max-w-[1112px]">
      <h1 className="font-display text-2xl leading-tight font-bold tracking-[-0.5px] text-ink sm:text-[28px]">
        {greeting()}
        {firstName && `, ${firstName}`}
      </h1>
      <p className="pt-1 text-sm text-body">
        {s?.matching_available ? "Your agent is scanning for you." : "Matching launches soon — for now we show open opportunities of the types you chose."}
      </p>

      {me.data.is_demo && (
        <Alert tone="info" className="mt-4">
          You&apos;re viewing the read-only demo. Saving is turned off.
        </Alert>
      )}

      {stats.isError && <Alert className="mt-4">We couldn&apos;t load your counts: {stats.error.message}</Alert>}

      <AskBar />

      <div className="grid gap-4 pt-5 lg:grid-cols-[1fr_400px]">
        <ProfileCard me={me.data} />
        <RadarCard stats={s} />
      </div>

      <div className="grid grid-cols-2 gap-3 pt-5 sm:flex sm:flex-wrap">
        <StatTile value={s?.for_you} label="open for you" />
        <StatTile value={s?.closing_this_week} label="closing this week" tone="warning" />
        <StatTile value={s?.saved} label="saved" />
        <StatTile value={s?.applications} label="my applications" tone="brand" />
      </div>

      <div role="tablist" aria-label="Opportunities" className="mt-5 flex gap-7 overflow-x-auto border-b border-line">
        {tabs.map((t) => (
          <button
            key={t.key}
            role="tab"
            type="button"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={cn("flex shrink-0 items-center gap-1.5 border-b-[3px] pt-3 pb-3 text-[15px]", tab === t.key ? "border-brand font-bold text-ink" : "border-transparent font-medium text-muted hover:text-ink")}
          >
            {t.label}
            {t.count !== undefined ? (
              <span className="rounded-full bg-brand-soft px-[7px] py-0.5 font-mono text-[11px] font-bold text-brand-strong">{t.count}</span>
            ) : (
              <Skeleton className="h-[17px] w-5 rounded-full" />
            )}
          </button>
        ))}
      </div>

      {tab === "applications" ? (
        <Empty title="No applications yet" body="When the Apply assistant ships, applications you submit through OppRadar will be tracked here." />
      ) : (
        <Feed tab={tab} q={q} type={type} setType={setType} profileTypes={me.data.opportunity_types} readOnly={me.data.is_demo} />
      )}
    </div>
  );
}

function Feed({ tab, q, type, setType, profileTypes, readOnly }: { tab: FeedTab; q: string; type: OpportunityType | null; setType: (t: OpportunityType | null) => void; profileTypes: OpportunityType[]; readOnly: boolean }) {
  const router = useRouter();
  const feed = useInfiniteQuery({
    queryKey: ["feed", tab, q, type],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => {
      const sp = new URLSearchParams({ tab, limit: String(PAGE), offset: String(pageParam) });
      if (q) sp.set("q", q);
      if (type) sp.set("type", type);
      return api<Page>(`/me/opportunities?${sp}`);
    },
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined),
  });
  const items = useMemo(() => feed.data?.pages.flatMap((p) => p.items) ?? [], [feed.data]);
  const total = feed.data?.pages[0]?.total ?? 0;
  const filtered = Boolean(q || type);

  return (
    <>
      <div className="flex flex-wrap gap-2 pt-3.5">
        <Chip active={!type} onClick={() => setType(null)}>
          All types
        </Chip>
        {profileTypes.map((t) => (
          <Chip key={t} active={type === t} onClick={() => setType(type === t ? null : t)}>
            {TYPE_LABELS[t]}
          </Chip>
        ))}
        {q && (
          <Chip active onClick={() => router.push("/dashboard")}>
            “{q}” ×
          </Chip>
        )}
        {filtered && (
          <button type="button" onClick={() => (setType(null), q && router.push("/dashboard"))} className="px-2 text-[13px] font-medium text-muted hover:text-ink">
            Clear filters
          </button>
        )}
      </div>

      <div className="flex flex-col gap-4 pt-[18px]">
        {feed.isPending && (
          <Loading label="Loading opportunities…" className="flex flex-col gap-4">
            <OpportunityCardSkeleton />
            <OpportunityCardSkeleton />
            <OpportunityCardSkeleton />
          </Loading>
        )}
        {feed.isError && <Alert>We couldn&apos;t load opportunities: {feed.error.message}</Alert>}
        {feed.isSuccess && items.length === 0 && (
          <Empty
            title={tab === "saved" ? "Nothing saved yet" : filtered ? "No results" : "Nothing open right now"}
            body={
              tab === "saved"
                ? "Press Save on an opportunity to keep it here."
                : filtered
                  ? "Try another search or clear the filters."
                  : "New opportunities are added as sources are scanned. Check back soon."
            }
          />
        )}
        {items.map((item) => (
          <OpportunityCard key={item.id} item={item} readOnly={readOnly} />
        ))}
        {feed.isFetchingNextPage && (
          <Loading label="Loading more…" className="flex flex-col gap-4">
            <OpportunityCardSkeleton />
            <OpportunityCardSkeleton />
          </Loading>
        )}
        {feed.hasNextPage && !feed.isFetchingNextPage && (
          <Button variant="outline" size="md" className="self-center" onClick={() => feed.fetchNextPage()} disabled={feed.isFetchingNextPage}>
            Show more ({total - items.length} left)
          </Button>
        )}
      </div>
    </>
  );
}

function AskBar() {
  return (
    <div className="mx-auto mt-4 flex max-w-[820px] items-center gap-2.5 rounded-card border border-line bg-surface px-3 py-2.5 opacity-80" title="Ask the agent — coming soon">
      <Image src="/icons/ask-sparkle.svg" alt="" width={18} height={18} />
      <input
        disabled
        placeholder="Ask the agent anything: paste a link or name an opportunity to check eligibility."
        aria-label="Ask the agent (coming soon)"
        className="min-w-0 flex-1 bg-transparent text-[15px] placeholder:text-faint"
      />
      <span className="hidden h-[26px] items-center rounded-full bg-brand-soft px-3 font-mono text-xs font-semibold text-brand-strong sm:flex">coming soon</span>
      <span className="flex size-11 shrink-0 items-center justify-center rounded-field bg-brand opacity-60">
        <Image src="/icons/arrow-right-white.svg" alt="" width={18} height={18} />
      </span>
    </div>
  );
}

function ProfileCard({ me }: { me: Me }) {
  const pct = Math.round((me.completeness ?? 0) * 100);
  const level = labelOf(EDUCATION_LEVELS, me.education_level);
  const year = me.current_year ? labelOf(CURRENT_YEARS, me.current_year) : null;
  const headline = [[level, me.field_of_study].filter(Boolean).join(" "), year, me.wilaya].filter(Boolean).join(" · ");
  const tip = me.completeness_suggestions[0] ?? nextTip(me);
  return (
    <section className="rounded-card border border-line bg-surface px-[22px] py-5 shadow-[0_1px_1.5px_rgb(30_17_62/0.05)]" aria-label="Your profile">
      <div className="flex items-center gap-3.5">
        <div className="flex size-[52px] shrink-0 items-center justify-center rounded-full bg-brand-soft text-lg font-bold text-brand-strong">{initialsOf(me.full_name || me.email)}</div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-[17px] font-bold text-ink">{me.full_name || me.email}</p>
          {headline && <p className="truncate pt-1 text-[13px] text-muted">{headline}</p>}
        </div>
        <ButtonLink href={isComplete(me) ? "/profile" : "/onboarding"} variant="outline" className="h-9 px-4 text-[13px]">
          Edit profile
        </ButtonLink>
      </div>
      {me.skills.length > 0 && (
        <div className="flex flex-wrap gap-2.5 pt-3.5">
          {me.skills.slice(0, 5).map((s) => <Pill key={s.id ?? s.name} className="h-8 text-xs">{s.name}</Pill>)}
        </div>
      )}
      <div className="flex items-center gap-3 pt-4">
        <div className="h-2 flex-1 overflow-hidden rounded bg-line" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Profile completeness">
          <div className="h-full rounded bg-brand" style={{ width: `${pct}%` }} />
        </div>
        <span className="font-mono text-xs font-semibold text-muted">{pct}%</span>
      </div>
      <p className="pt-1.5 text-xs text-muted">
        {!isComplete(me) ? "Finish setting up your profile so the agent can match you." : tip && pct < 100 ? `Almost there — ${tip}` : "Your profile is complete."}
      </p>
    </section>
  );
}

/** First optional section still empty (mirrors completeness() in backend/app/services/profiles.py). */
function nextTip(me: Me): string | null {
  if (!me.links.length) return "add a portfolio or GitHub link — agents match better with links.";
  if (!me.experiences.length && !me.certificates.length) return "add an experience or a certificate.";
  if (!me.skills.some((s) => s.level)) return "set a level for your skills.";
  if (!me.languages.length) return "add the languages you speak.";
  if (!me.institution) return "add your institution to find campus opportunities.";
  return null;
}

function RadarCard({ stats }: { stats?: Stats }) {
  if (!stats) return <RadarCardSkeleton />;
  const live = stats.matching_available;
  return (
    <section className="rounded-card border border-line bg-[linear-gradient(153deg,#fff_60%,#f6f2fc_100%)] px-[22px] py-5 shadow-[0_1px_1.5px_rgb(30_17_62/0.05)]" aria-label="Your agent">
      <div className="flex items-center justify-between gap-3">
        <p className="flex items-center gap-2.5 text-[15px] font-bold text-ink">
          <span className={cn("size-2.5 rounded-full", live ? "bg-success shadow-[0_0_0_4px_#ecfdf5]" : "bg-warning shadow-[0_0_0_4px_#fffbeb]")} />
          {live ? "Radar active" : stats.agent_started_at ? "Agent ready" : "Agent not started"}
        </p>
        <span className="font-mono text-xs text-muted">{live ? "scanning" : "matching soon"}</span>
      </div>
      <div className="mt-3 rounded-field bg-night px-[18px] py-4 font-mono text-[11px] leading-[20.9px] text-on-night-strong">
        <p>
          <span className="text-[#8b7fb0]">now :</span> {stats.for_you} open opportunities fit your types
        </p>
        <p>
          <span className="text-[#8b7fb0]">now :</span> {stats.closing_this_week} close in the next 7 days
        </p>
        {!live && (
          <p>
            <span className="text-[#8b7fb0]">soon:</span> match scores + eligibility checks
          </p>
        )}
      </div>
      <div className="flex gap-2.5 pt-3.5">
        <Button className="h-10 flex-1 text-sm" disabled title="Available when matching launches">
          Run scan now
        </Button>
        <Button variant="ghost" className="h-10 text-sm" disabled title="Available when matching launches">
          History
        </Button>
      </div>
    </section>
  );
}

function StatTile({ value, label, tone }: { value?: number; label: string; tone?: "warning" | "brand" }) {
  return (
    <div className="flex items-center gap-3 rounded-card border border-line bg-surface px-[18px] py-3.5">
      <span className={cn("font-mono text-[26px] font-semibold", tone === "warning" ? "text-warning" : tone === "brand" ? "text-brand" : "text-ink")}>{value ?? <Skeleton className="h-7 w-7" />}</span>
      <span className="text-xs font-bold tracking-[0.8px] text-muted uppercase">{label}</span>
    </div>
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

function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="mt-[18px] rounded-card border border-dashed border-line bg-surface px-6 py-10 text-center">
      <p className="text-base font-bold text-ink">{title}</p>
      <p className="mx-auto max-w-md pt-1.5 text-sm text-muted">{body}</p>
    </div>
  );
}

function RadarCardSkeleton() {
  return (
    <Loading label="Loading your agent…" className="rounded-card border border-line bg-surface px-[22px] py-5">
      <div className="flex justify-between">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-4 w-24" />
      </div>
      <Skeleton className="mt-3 h-[86px] w-full rounded-field" />
      <div className="flex gap-2.5 pt-3.5">
        <Skeleton className="h-10 flex-1 rounded-field" />
        <Skeleton className="h-10 w-20 rounded-field" />
      </div>
    </Loading>
  );
}

/** First load: the dashboard's shape before the profile arrives. */
function DashboardSkeleton() {
  return (
    <Loading label="Loading your dashboard…" className="mx-auto max-w-[1112px]">
      <Skeleton className="h-8 w-72" />
      <Skeleton className="mt-2.5 h-4 w-96 max-w-full" />
      <Skeleton className="mx-auto mt-5 h-[66px] max-w-[820px] rounded-card" />
      <div className="grid gap-4 pt-5 lg:grid-cols-[1fr_400px]">
        <div className="rounded-card border border-line bg-surface px-[22px] py-5">
          <div className="flex items-center gap-3.5">
            <Skeleton className="size-[52px] rounded-full" />
            <div className="flex-1">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="mt-2 h-3.5 w-56" />
            </div>
            <Skeleton className="h-9 w-24 rounded-field" />
          </div>
          <div className="flex gap-2.5 pt-3.5">
            {["w-16", "w-12", "w-24", "w-14"].map((w) => <Skeleton key={w} className={`h-8 rounded-full ${w}`} />)}
          </div>
          <Skeleton className="mt-4 h-2 w-full rounded" />
          <Skeleton className="mt-2.5 h-3 w-2/3" />
        </div>
        <RadarCardSkeleton />
      </div>
      <div className="grid grid-cols-2 gap-3 pt-5 sm:flex">
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[62px] rounded-card sm:w-52" />)}
      </div>
      <Skeleton className="mt-6 h-10 w-full max-w-lg" />
      <div className="flex flex-col gap-4 pt-[18px]">
        <OpportunityCardSkeleton />
        <OpportunityCardSkeleton />
      </div>
    </Loading>
  );
}
