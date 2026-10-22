"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Pill, SectionLabel } from "@/components/ui/inputs";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { ApiError, api, type Me } from "@/lib/api/client";
import { STATUS, useApplications } from "@/lib/applications";
import { useOpportunityAction } from "@/lib/hooks/use-opportunity-actions";
import {
  SCAM_FLAG_TEXT,
  TYPE_LABELS,
  deadlineText,
  formatDate,
  languageLabel,
  modeLabel,
  sourceHost,
  type MyOpportunity,
} from "@/lib/opportunities";
import { cn } from "@/lib/utils";

const TRUST: Record<string, { label: string; tone: string }> = {
  verified: { label: "Verified source", tone: "bg-[#ecfdf5] text-success" },
  likely_safe: { label: "Looks legitimate", tone: "bg-[#ecfdf5] text-success" },
  unknown: { label: "Source not verified yet", tone: "bg-page text-body" },
  suspicious: { label: "Suspicious — check carefully", tone: "bg-[#fffbeb] text-warning" },
  scam: { label: "Likely scam — don't share personal data", tone: "bg-danger-soft text-danger" },
};

export function OpportunityDetail({ id }: { id: string }) {
  const opp = useQuery({ queryKey: ["opportunity", id], queryFn: () => api<MyOpportunity>(`/me/opportunities/${id}`) });
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });

  if (opp.isPending) return <DetailSkeleton />;
  if (opp.isError) {
    const missing = opp.error instanceof ApiError && opp.error.status === 404;
    return (
      <div className="mx-auto max-w-[1032px]">
        <Alert>{missing ? "This opportunity doesn't exist or was removed." : `We couldn't load it: ${opp.error.message}`}</Alert>
        <Link href="/dashboard" className="mt-4 inline-block text-sm font-bold text-brand">
          &lt; Back to the dashboard
        </Link>
      </div>
    );
  }

  const o = opp.data;
  const deadline = deadlineText(o.deadline);
  const place = [o.location, o.country].filter((p, i, a) => p && a.indexOf(p) === i).join(", ");
  const trust = TRUST[o.trust_level] ?? TRUST.unknown;

  return (
    <div className="mx-auto max-w-[1032px]">
      <nav aria-label="Breadcrumb" className="text-[13px] text-muted">
        <Link href="/dashboard" className="font-bold text-ink hover:text-brand">
          Dashboard
        </Link>{" "}
        / <span className="text-ink">{o.title}</span>
      </nav>

      <div className="flex flex-col gap-4 pt-5 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Pill className="h-8 px-4 text-sm">{TYPE_LABELS[o.type]}</Pill>
            {o.is_new && (
              <span className="flex h-8 items-center gap-1.5 rounded-full bg-signal px-3.5 text-[13px] font-bold text-ink">
                <Image src="/icons/sparkle-dark.svg" alt="" width={13} height={13} />
                New
              </span>
            )}
          </div>
          <h1 className="pt-3 font-display text-3xl leading-tight font-bold tracking-[-0.5px] text-ink sm:text-[38px]">{o.title}</h1>
          <p className="flex flex-wrap items-center gap-x-4 gap-y-1 pt-2 text-[15px] text-muted">
            <span>{["Organized by " + o.organizer, place, o.funding].filter(Boolean).join(" · ")}</span>
            {o.url && (
              <a href={o.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-[13px] font-bold text-ink hover:text-brand">
                <Image src="/icons/external-light.svg" alt="" width={13} height={13} className="invert" />
                Official page ↗
              </a>
            )}
          </p>
        </div>
        <p className={cn("flex shrink-0 items-center gap-2 text-base font-bold md:pt-2", deadline.urgent ? "text-warning" : "text-ink")}>
          <Image src={deadline.urgent ? "/icons/clock-orange.svg" : "/icons/clock-dark.svg"} alt="" width={16} height={16} />
          {deadline.text}
        </p>
      </div>

      <div className="grid gap-5 pt-6 lg:grid-cols-[1fr_334px]">
        <div className="flex min-w-0 flex-col gap-5">
          <Card>
            <h2 className="text-xl font-bold text-ink">About this opportunity</h2>
            <p className="pt-2 text-[15px] leading-relaxed text-body">{o.summary || "No description yet — open the official page for details."}</p>

            <SectionLabel className="pt-6">Requirements (from the official page)</SectionLabel>
            {o.eligibility.length ? (
              <ul className="mt-2 divide-y divide-line border-y border-line">
                {o.eligibility.map((req) => (
                  <li key={req} className="flex items-center justify-between gap-3 py-3 text-[15px] text-ink">
                    <span>{req}</span>
                    <span className="shrink-0 rounded-full bg-page px-3 py-1 text-xs font-bold text-muted">check soon</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="pt-2 text-sm text-muted">No requirements listed. Check the official page.</p>
            )}
            <p className="pt-3 text-xs text-muted">
              The agent will check each requirement against your profile once matching launches. For now, compare them yourself.
            </p>

            {o.benefits.length > 0 && (
              <>
                <SectionLabel className="pt-6">What you get</SectionLabel>
                <div className="flex flex-wrap gap-2 pt-2">
                  {o.benefits.map((b) => <Pill key={b} muted className="h-8">{b}</Pill>)}
                </div>
              </>
            )}
          </Card>

          <Card>
            <h2 className="text-lg font-bold text-ink">Key facts</h2>
            <dl className="grid grid-cols-2 gap-4 pt-3 sm:grid-cols-5">
              <Fact label="Deadline" value={o.deadline ? formatDate(o.deadline, true) : "Rolling"} />
              <Fact label="Location" value={[place, modeLabel(o.mode)].filter(Boolean).join(" · ") || "—"} />
              <Fact label="Benefit" value={o.funding || "—"} mono />
              <Fact label="Type" value={TYPE_LABELS[o.type]} />
              <Fact label="Language" value={languageLabel(o.language)} />
            </dl>
          </Card>

          <Card>
            <h2 className="text-lg font-bold text-ink">Source &amp; safety</h2>
            <p className={cn("mt-3 inline-flex rounded-full px-3 py-1 text-[13px] font-bold", trust.tone)}>{trust.label}</p>
            {o.scam_flags.length > 0 && (
              <ul className="mt-3 flex flex-col gap-1.5">
                {o.scam_flags.map((f, i) => {
                  const flag = String((f as { flag?: string }).flag ?? "");
                  const detail = String((f as { detail?: string }).detail ?? "");
                  return (
                    <li key={i} className="flex gap-2 text-sm text-danger">
                      <Image src="/icons/x-circle-red.svg" alt="" width={14} height={14} className="mt-0.5 shrink-0" />
                      <span>
                        {SCAM_FLAG_TEXT[flag] ?? flag}
                        {detail && <span className="text-body"> — {detail}</span>}
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
            <Alert tone="info" className="mt-4 text-[13px]">
              OppRadar never asks for payment or bank details. Always verify dates and requirements on the official page before applying.
            </Alert>
          </Card>

          <p className="flex flex-wrap justify-between gap-2 text-xs text-muted">
            <span>
              <strong className="text-body">Always verify on the official page.</strong>
            </span>
            {o.url && <span className="font-mono">source: {sourceHost(o.url)} ↗</span>}
          </p>
        </div>

        <NextSteps o={o} readOnly={me.data?.is_demo ?? true} />
      </div>
    </div>
  );
}

function NextSteps({ o, readOnly }: { o: MyOpportunity; readOnly: boolean }) {
  const router = useRouter();
  const action = useOpportunityAction();
  const applied = useApplications().data?.find((a) => a.opportunity_id === o.id);
  const busy = action.isPending;
  const soon = "Coming with the AI agent";

  return (
    <aside className="flex flex-col gap-2.5 self-start rounded-card border border-line bg-surface p-5 shadow-card lg:sticky lg:top-24">
      <SectionLabel>Your next steps</SectionLabel>
      {o.url ? (
        <a href={o.url} target="_blank" rel="noopener noreferrer" className="flex h-12 items-center justify-center rounded-field bg-brand px-4 text-base font-bold text-white hover:bg-brand-strong">
          Apply on official site ↗
        </a>
      ) : (
        <p className="text-sm text-muted">No official link yet.</p>
      )}
      {applied ? (
        <Link href="/applications" className="flex h-12 items-center justify-center gap-2 rounded-field border border-line px-4 text-[15px] font-bold text-ink hover:bg-page">
          <span className={cn("rounded-full px-2.5 py-0.5 text-xs", STATUS[applied.status].tone)}>{STATUS[applied.status].label}</span>
          View my application
        </Link>
      ) : (
        <Link href={`/apply/${o.id}`} className="flex h-12 items-center justify-center rounded-field border border-brand px-4 text-[15px] font-bold text-brand hover:bg-brand-soft">
          Apply assistant
        </Link>
      )}
      <p className="flex items-center justify-center gap-1.5 rounded-field bg-page px-3 py-2 text-xs font-bold text-body">
        <Image src="/icons/lock-dark.svg" alt="" width={12} height={12} />
        Nothing is sent until you press Submit
      </p>

      {!readOnly && (
        <Button variant="ghost" size="md" disabled={busy} aria-pressed={o.saved} onClick={() => action.mutate({ id: o.id, flag: "saved", on: !o.saved })} className="text-ink">
          <Image src="/icons/bookmark-purple.svg" alt="" width={15} height={15} />
          {o.saved ? "Saved — remove" : "Save"}
        </Button>
      )}
      <Button variant="ghost" size="md" disabled title={soon}>
        Remind me 3 days before · soon
      </Button>
      <Button variant="ghost" size="md" disabled title={soon}>
        Ask the agent about this · soon
      </Button>
      {!readOnly && (
        <Button
          variant="ghost"
          size="md"
          className="text-muted"
          disabled={busy}
          onClick={async () => {
            if (o.dismissed) return action.mutate({ id: o.id, flag: "dismissed", on: false });
            await action.mutateAsync({ id: o.id, flag: "dismissed", on: true });
            router.push("/dashboard");
          }}
        >
          {o.dismissed ? "Show it again in my feed" : "Not interested"}
        </Button>
      )}
      {action.isError && <p className="text-center text-xs text-danger">Couldn&apos;t update. Try again.</p>}
    </aside>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return <section className="rounded-card border border-line bg-surface p-5 shadow-[0_1px_1.5px_rgb(30_17_62/0.05)] sm:p-7">{children}</section>;
}

function Fact({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-bold tracking-[0.8px] text-muted uppercase">{label}</dt>
      <dd className={cn("pt-1 text-[15px] font-bold break-words text-ink", mono && "font-mono")}>{value}</dd>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <Loading label="Loading the opportunity…" className="mx-auto max-w-[1032px]">
      <Skeleton className="h-4 w-56" />
      <div className="flex flex-col gap-4 pt-5 md:flex-row md:justify-between">
        <div className="flex-1">
          <Skeleton className="h-8 w-28 rounded-full" />
          <Skeleton className="mt-4 h-10 w-3/4" />
          <Skeleton className="mt-3 h-4 w-1/2" />
        </div>
        <Skeleton className="h-6 w-56" />
      </div>
      <div className="grid gap-5 pt-6 lg:grid-cols-[1fr_334px]">
        <div className="flex flex-col gap-5">
          <div className="rounded-card border border-line bg-surface p-5 sm:p-7">
            <Skeleton className="h-6 w-56" />
            <Skeleton className="mt-3 h-4 w-full" />
            <Skeleton className="mt-2 h-4 w-11/12" />
            <Skeleton className="mt-2 h-4 w-2/3" />
            <Skeleton className="mt-7 h-3 w-48" />
            {[0, 1, 2].map((i) => <Skeleton key={i} className="mt-3 h-10 w-full" />)}
          </div>
          <div className="rounded-card border border-line bg-surface p-5 sm:p-7">
            <Skeleton className="h-5 w-28" />
            <div className="grid grid-cols-2 gap-4 pt-4 sm:grid-cols-5">
              {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-10" />)}
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-2.5 self-start rounded-card border border-line bg-surface p-5">
          <Skeleton className="h-3 w-32" />
          <Skeleton className="h-12 w-full rounded-field" />
          <Skeleton className="h-12 w-full rounded-field" />
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="mx-auto h-5 w-40" />)}
        </div>
      </div>
    </Loading>
  );
}
