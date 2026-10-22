"use client";

import Link from "next/link";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Select } from "@/components/ui/inputs";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { STATUS, useApplications, useRemoveApplication, useSaveApplication, type Application, type ApplicationStatus } from "@/lib/applications";
import { TYPE_LABELS } from "@/lib/opportunities";
import { cn } from "@/lib/utils";

/** Tracked applications with editable status — used on /applications and the dashboard tab. */
export function ApplicationList({ readOnly }: { readOnly: boolean }) {
  const apps = useApplications();

  if (apps.isError) return <Alert>We couldn&apos;t load your applications: {apps.error.message}</Alert>;
  if (apps.isPending)
    return (
      <Loading label="Loading applications…" className="flex flex-col gap-3">
        {[0, 1].map((i) => <Skeleton key={i} className="h-[104px] rounded-card" />)}
      </Loading>
    );
  if (!apps.data.length)
    return (
      <div className="rounded-card border border-dashed border-line bg-surface px-6 py-10 text-center">
        <p className="text-base font-bold text-ink">No applications yet</p>
        <p className="mx-auto max-w-md pt-1.5 text-sm text-muted">
          Open an opportunity and use the <strong>Apply assistant</strong>: it prepares your answers, sends you to the official form, and records the application here.
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
            {o && <span className="rounded-full bg-brand-soft px-3 py-0.5 text-xs font-bold text-brand-strong">{TYPE_LABELS[o.type]}</span>}
            <span className={cn("rounded-full px-3 py-0.5 text-xs font-bold", status.tone)}>{status.label}</span>
          </div>
          <p className="pt-2 text-[17px] font-bold text-ink">
            {o ? (
              <Link href={`/opportunities/${o.id}`} className="hover:text-brand-strong">
                {o.title}
              </Link>
            ) : (
              "Opportunity removed"
            )}
          </p>
          <p className="text-[13px] text-muted">
            {[o?.organizer, a.submitted_at && `submitted ${new Date(a.submitted_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })}`].filter(Boolean).join(" · ")}
          </p>
        </div>
        {!readOnly && (
          <div className="flex flex-wrap items-center gap-2">
            <Select
              aria-label="Application status"
              value={a.status}
              disabled={save.isPending}
              onChange={(e) => save.mutate({ opportunityId: a.opportunity_id, body: { status: e.target.value as ApplicationStatus } })}
              className="h-10 w-auto min-w-40 text-sm"
            >
              {(Object.keys(STATUS) as ApplicationStatus[]).map((s) => (
                <option key={s} value={s}>
                  {STATUS[s].label}
                </option>
              ))}
            </Select>
            <button
              type="button"
              onClick={() => window.confirm("Stop tracking this application?") && remove.mutate(a.opportunity_id)}
              className="px-2 text-[13px] font-bold text-muted hover:text-danger"
            >
              Remove
            </button>
          </div>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2 pt-3">
        <label className="text-xs font-bold text-muted" htmlFor={`ref-${a.id}`}>
          Reference
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
          <a href={o.url} target="_blank" rel="noopener noreferrer" className="ml-auto text-[13px] font-bold text-body hover:text-ink">
            Official page ↗
          </a>
        )}
      </div>
      {(save.isError || remove.isError) && <p className="pt-2 text-xs text-danger">Couldn&apos;t update. Try again.</p>}
    </li>
  );
}
