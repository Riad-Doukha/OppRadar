"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button, ButtonLink, Spinner } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { SectionLabel } from "@/components/ui/inputs";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { ApiError, api, type Me } from "@/lib/api/client";
import { STATUS, useApplications, useSaveApplication, type Application } from "@/lib/applications";
import { CURRENT_YEARS, EDUCATION_LEVELS, labelOf } from "@/lib/onboarding/options";
import { deadlineText, type MyOpportunity } from "@/lib/opportunities";
import { cn } from "@/lib/utils";

const STEPS = ["Your answers", "Apply on the official site", "Record it"];

/**
 * Apply assistant (Figma flow: review answers → captcha → submit). The agent
 * that fills organizer forms isn't shipped; today it prepares your answers to
 * copy, sends you to the official form, and records the application.
 */
export function ApplyPage({ id }: { id: string }) {
  const opp = useQuery({ queryKey: ["opportunity", id], queryFn: () => api<MyOpportunity>(`/me/opportunities/${id}`) });
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  const apps = useApplications();
  const existing = apps.data?.find((a) => a.opportunity_id === id);
  const [recorded, setRecorded] = useState<Application | null>(null);

  if (opp.isError) {
    const missing = opp.error instanceof ApiError && opp.error.status === 404;
    return <Alert>{missing ? "This opportunity doesn't exist or was removed." : `We couldn't load it: ${opp.error.message}`}</Alert>;
  }
  if (!opp.data || !me.data) {
    return (
      <Loading label="Loading the apply assistant…" className="mx-auto max-w-[1032px]">
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
        Apply assistant · <span className="font-bold text-ink">{o.title}</span>
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
  return (
    <ol className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2 pt-4" aria-label="Steps">
      {STEPS.map((label, i) => (
        <li key={label} className="flex items-center gap-2.5" aria-current={i === current ? "step" : undefined}>
          {i > 0 && <span className="hidden h-px w-10 bg-line sm:block" aria-hidden />}
          <span
            className={cn(
              "flex size-7 items-center justify-center rounded-full border text-xs font-bold",
              i < current || current === 2 ? "border-brand bg-brand text-white" : i === current ? "border-ink bg-signal text-ink" : "border-line text-muted",
            )}
          >
            {i < current || current === 2 ? "✓" : i + 1}
          </span>
          <span className={cn("text-[13px]", i === current ? "font-bold text-ink" : "text-muted")}>{label}</span>
        </li>
      ))}
    </ol>
  );
}

/** Profile answers most forms ask for, ready to copy. */
function Answers({ me }: { me: Me }) {
  const link = (kind: string) => me.links.find((l) => l.kind === kind)?.url;
  const rows: [string, string | null | undefined][] = [
    ["Full name", me.full_name],
    ["Email", me.email],
    ["Birth year", me.birth_year?.toString()],
    ["Nationality", me.nationality],
    ["Location", [me.wilaya, me.country].filter(Boolean).join(", ")],
    ["University", me.institution],
    ["Education level", labelOf(EDUCATION_LEVELS, me.education_level)],
    ["Field of study", me.field_of_study],
    ["Current year", me.current_year ? labelOf(CURRENT_YEARS, me.current_year) : null],
    ["Graduation year", me.graduation_year?.toString()],
    ["Languages", me.languages.map((l) => `${l.language} (${l.level})`).join(", ")],
    ["Skills", me.skills.map((s) => s.name).join(", ")],
    ["LinkedIn", link("linkedin")],
    ["GitHub", link("github")],
    ["Portfolio", link("portfolio")],
    ["Goal (starting point for a motivation)", me.goal],
  ];
  const filled = rows.filter(([, v]) => v);

  return (
    <section className="rounded-card border border-line bg-surface p-5 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="font-display text-xl font-bold text-ink">Your answers, ready to copy</h1>
        <span className="rounded-full bg-brand-soft px-3 py-1 font-mono text-xs font-semibold text-brand-strong">{filled.length} from your profile</span>
      </div>
      <p className="pt-1 text-[13px] text-muted">
        Paste them into the organizer&apos;s form. Answers drafted by the agent (motivation letters, form-specific questions) arrive with the AI agent.
      </p>
      <dl className="flex flex-col gap-3 pt-5">
        {filled.map(([label, value]) => (
          <CopyRow key={label} label={label} value={value!} />
        ))}
      </dl>
      {filled.length < rows.length && (
        <p className="pt-4 text-xs text-muted">
          Some answers are empty —{" "}
          <Link href="/profile" className="font-bold text-brand">
            complete your profile
          </Link>
          .
        </p>
      )}
    </section>
  );
}

function CopyRow({ label, value }: { label: string; value: string }) {
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
          <span className="size-1.5 rounded-full bg-brand" aria-hidden /> From your profile
        </span>
      </div>
      <dd className="flex items-start gap-2 rounded-field border border-line bg-surface px-3.5 py-2.5">
        <span className="min-w-0 flex-1 text-[15px] break-words text-ink select-all">{value}</span>
        <button type="button" onClick={copy} className="shrink-0 text-xs font-bold text-brand hover:text-brand-strong" aria-label={`Copy ${label}`}>
          {copied ? "Copied ✓" : "Copy"}
        </button>
      </dd>
    </div>
  );
}

function Submit({ o, readOnly, onRecorded }: { o: MyOpportunity; readOnly: boolean; onRecorded: (a: Application) => void }) {
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
      <SectionLabel>Applying to</SectionLabel>
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
          Open the official form ↗
        </a>
      ) : (
        <p className="text-sm text-muted">No official link yet.</p>
      )}
      <p className="flex items-center justify-center gap-1.5 rounded-field bg-page px-3 py-2 text-center text-xs font-bold text-body">
        <Image src="/icons/lock-dark.svg" alt="" width={12} height={12} />
        OppRadar never submits for you — you submit on the organizer&apos;s site
      </p>

      {!readOnly && (
        <form onSubmit={record} className={cn("mt-1 flex flex-col gap-2.5 border-t border-line pt-4", !opened && "opacity-90")}>
          <p className="text-sm font-bold text-ink">Done on the official site?</p>
          <Input value={reference} onChange={(e) => setReference(e.target.value)} maxLength={120} placeholder="Reference / receipt number (optional)" aria-label="Reference number" />
          <Button type="submit" variant="outline" size="md" disabled={save.isPending}>
            {save.isPending && <Spinner />} I&apos;ve submitted it
          </Button>
          {save.isError && <p className="text-xs text-danger">Couldn&apos;t record it: {save.error.message}</p>}
          <p className="text-xs text-muted">We&apos;ll track it on your Applications page and remind you to update its status.</p>
        </form>
      )}
      <Link href={`/opportunities/${o.id}`} className="pt-1 text-center text-[13px] font-bold text-body hover:text-ink">
        ‹ Back to the opportunity
      </Link>
    </aside>
  );
}

function Recorded({ o, app }: { o: MyOpportunity; app: Application }) {
  const status = STATUS[app.status];
  return (
    <section className="mx-auto mt-6 max-w-[540px] rounded-card border border-line bg-surface p-6 text-center shadow-card sm:p-9">
      <div className="mx-auto flex size-16 items-center justify-center rounded-full bg-[#ecfdf5]">
        <Image src="/icons/check-green.svg" alt="" width={30} height={30} />
      </div>
      <h1 className="pt-4 font-display text-2xl font-bold text-ink">Application recorded</h1>
      <p className="pt-2 text-[15px] text-body">
        Your application to <strong className="text-ink">{o.title}</strong> is on your Applications page. Update it when you hear back.
      </p>
      <dl className="mt-5 grid grid-cols-2 gap-4 rounded-field border border-line bg-page/60 p-4 text-left">
        <div>
          <dt className="text-[11px] font-bold tracking-[0.8px] text-muted uppercase">Reference</dt>
          <dd className="pt-0.5 font-mono text-sm font-bold text-ink">{app.reference || "—"}</dd>
        </div>
        <div>
          <dt className="text-[11px] font-bold tracking-[0.8px] text-muted uppercase">Recorded</dt>
          <dd className="pt-0.5 text-sm font-bold text-ink">
            {app.submitted_at ? new Date(app.submitted_at).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] font-bold tracking-[0.8px] text-muted uppercase">Submitted on</dt>
          <dd className="pt-0.5 text-sm font-bold text-ink">The official site</dd>
        </div>
        <div>
          <dt className="text-[11px] font-bold tracking-[0.8px] text-muted uppercase">Status</dt>
          <dd className="pt-1">
            <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-bold", status.tone)}>{status.label}</span>
          </dd>
        </div>
      </dl>
      <div className="flex flex-wrap justify-center gap-2.5 pt-6">
        <ButtonLink href="/applications" size="md">
          Go to my applications →
        </ButtonLink>
        {o.url && (
          <a href={o.url} target="_blank" rel="noopener noreferrer" className="flex h-12 items-center px-3 text-[15px] font-bold text-body hover:text-ink">
            Open official page ↗
          </a>
        )}
      </div>
    </section>
  );
}
