"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import { initialsOf } from "@/components/app/app-shell";
import { Alert } from "@/components/ui/alert";
import { Button, ButtonLink } from "@/components/ui/button";
import { Pill, SectionLabel } from "@/components/ui/inputs";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { api, type Me } from "@/lib/api/client";
import {
  AVAILABILITY,
  CURRENT_YEARS,
  EDUCATION_LEVELS,
  EXPERIENCE_KINDS,
  FREQUENCIES,
  PREFERRED_LOCATIONS,
  labelOf,
} from "@/lib/onboarding/options";
import { firstIncompleteStep, isComplete } from "@/lib/onboarding/status";
import { TYPE_LABELS } from "@/lib/opportunities";
import { cn } from "@/lib/utils";

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const edit = (step: number) => `/onboarding?step=${step}`;

/** "My profile" (Figma): the whole profile at a glance; each Edit opens that wizard step. */
export function ProfilePage() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });

  if (me.isError) return <Alert>We couldn&apos;t load your profile: {me.error.message}</Alert>;
  if (!me.data) return <ProfileSkeleton />;
  const p = me.data;
  const complete = isComplete(p);
  const pct = Math.round(p.completeness * 100);

  function download() {
    // Everything we store about the profile, as the API returns it.
    const blob = new Blob([JSON.stringify(p, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), { href: url, download: "oppradar-profile.json" });
    a.click();
    URL.revokeObjectURL(url);
  }

  const headline = [
    [p.current_year && labelOf(CURRENT_YEARS, p.current_year).replace(" year", "-year"), p.field_of_study].filter(Boolean).join(" "),
    [p.institution, p.wilaya].filter(Boolean).join(", "),
    p.graduation_year && `graduating ${p.graduation_year}`,
  ].filter(Boolean).join(" · ");

  const age = p.birth_year ? new Date().getFullYear() - p.birth_year : null;
  const n = p.notifications;
  const link = (kind: string) => p.links.find((l) => l.kind === kind)?.url;

  return (
    <div className="mx-auto max-w-[1112px]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-2xl font-bold tracking-[-0.5px] text-ink sm:text-[28px]">My profile</h1>
        <div className="flex gap-2.5">
          <Button variant="ghost" className="h-10 text-sm" onClick={download}>
            Download my data
          </Button>
          {!p.is_demo && (
            <ButtonLink href={edit(1)} variant="outline" className="h-10 text-sm">
              Re-upload CV
            </ButtonLink>
          )}
        </div>
      </div>

      {p.is_demo && (
        <Alert tone="info" className="mt-4">
          This is the read-only demo profile. Editing is turned off.
        </Alert>
      )}

      {/* Header card */}
      <section className="mt-4 flex flex-col gap-5 rounded-card border border-line bg-surface px-5 py-6 shadow-[0_1px_1.5px_rgb(30_17_62/0.05)] sm:px-7 md:flex-row md:items-center">
        <div className="flex size-[76px] shrink-0 items-center justify-center rounded-full bg-brand-soft text-[26px] font-bold text-brand-strong">{initialsOf(p.full_name || p.email)}</div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <p className="font-display text-[22px] font-bold text-ink">{p.full_name || p.email}</p>
            <span className={cn("flex h-7 items-center rounded-full px-3 text-[13px] font-bold", complete ? "bg-[#ecfdf5] text-success" : "bg-[#fffbeb] text-warning")}>
              {complete ? "Ready" : "Incomplete"}
            </span>
          </div>
          {headline && <p className="pt-1 text-[13px] text-muted">{headline}</p>}
          {p.skills.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-2.5">
              {p.skills.slice(0, 4).map((s) => <Pill key={s.id ?? s.name} className="h-[26px] text-xs">{s.name}</Pill>)}
              {p.skills.length > 4 && <Pill muted className="h-[26px] text-xs">+{p.skills.length - 4} more</Pill>}
            </div>
          )}
        </div>
        <div className="w-full shrink-0 md:w-[260px]">
          <div className="flex items-baseline justify-between">
            <SectionLabel>Completeness</SectionLabel>
            <span className="font-mono text-base font-bold text-ink">{pct}%</span>
          </div>
          <div className="mt-1.5 h-[9px] overflow-hidden rounded-[5px] bg-line" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Profile completeness">
            <div className="h-full rounded-[5px] bg-brand" style={{ width: `${pct}%` }} />
          </div>
          <p className="pt-2 text-xs text-muted">
            {!complete ? (
              <>
                Some required fields are missing —{" "}
                <Link href={edit(firstIncompleteStep(p))} className="text-[13px] font-bold text-brand">
                  continue setup
                </Link>
              </>
            ) : pct < 100 ? (
              <>
                {missingOptional(p)} —{" "}
                <Link href={edit(missingOptionalStep(p))} className="text-[13px] font-bold text-brand">
                  add it
                </Link>
              </>
            ) : (
              "Your profile is complete."
            )}
          </p>
        </div>
      </section>

      <div className="grid gap-4 pt-[18px] md:grid-cols-2">
        <Card icon="section-about" title="About you" step={1} readOnly={p.is_demo}>
          <Facts
            rows={[
              ["Full name", p.full_name],
              ["Birth year", p.birth_year ? `${p.birth_year} (${age})` : null],
              ["Nationality", p.nationality],
              ["Location", [p.wilaya, p.country].filter(Boolean).join(", ")],
              ["Languages", p.languages.map((l) => `${l.language} ${l.level}`).join(" · ")],
            ]}
          />
        </Card>

        <Card icon="section-education" title="Education" step={2} readOnly={p.is_demo}>
          <Facts
            rows={[
              ["Level", labelOf(EDUCATION_LEVELS, p.education_level)],
              ["Field", p.field_of_study],
              ["Institution", p.institution],
              ["Year", [p.current_year && labelOf(CURRENT_YEARS, p.current_year), p.graduation_year && `graduating ${p.graduation_year}`].filter(Boolean).join(" · ")],
              ["GPA", p.gpa_value != null ? `${p.gpa_value} / ${p.gpa_scale}` : null],
            ]}
          />
        </Card>

        <Card icon="section-experience" title="Experience" step={2} readOnly={p.is_demo}>
          {p.experiences.length + p.certificates.length === 0 ? (
            <Empty step={2}>No experience or certificates yet</Empty>
          ) : (
            <div className="flex flex-col gap-[9px]">
              {p.experiences.map((x) => (
                <div key={x.id} className="rounded-field border border-line px-3.5 py-[11px]">
                  <div className="flex flex-wrap items-center gap-[9px]">
                    <Pill className="h-[23px] text-[11px]">{labelOf(EXPERIENCE_KINDS, x.kind)}</Pill>
                    <span className="text-[14.5px] font-bold text-ink">{[x.title, x.organization].filter(Boolean).join(" — ")}</span>
                    {x.year && <span className="font-mono text-xs text-muted">{x.year}</span>}
                  </div>
                  {x.description && <p className="pt-1 text-[13px] text-body">{x.description}</p>}
                </div>
              ))}
              {p.certificates.map((c) => (
                <div key={c.id} className="rounded-field border border-line bg-[#fbfafe] px-3.5 py-[11px]">
                  <p className="text-[14.5px] font-bold text-body">{[c.title, c.issuer].filter(Boolean).join(" — ")}</p>
                  <p className="text-[13px] text-body">
                    Certificate{c.year ? ` · ${c.year}` : ""}
                    {c.credential_url && (
                      <>
                        {" · "}
                        <a href={c.credential_url} target="_blank" rel="noopener noreferrer" className="font-bold text-brand">
                          credential ↗
                        </a>
                      </>
                    )}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card icon="section-skills" title="Skills & interests" step={3} readOnly={p.is_demo}>
          <SectionLabel>Skills</SectionLabel>
          <div className="flex flex-wrap gap-[7px] pt-2">
            {p.skills.length ? p.skills.map((s) => <Pill key={s.id ?? s.name} className="h-8 text-[12.5px]">{s.name}{s.level && ` · ${cap(s.level)}`}</Pill>) : <Empty step={3}>No skills yet</Empty>}
          </div>
          <SectionLabel className="pt-4">Interests</SectionLabel>
          <div className="flex flex-wrap gap-[7px] pt-2">
            {p.interests.length ? p.interests.map((i) => <Pill key={i} muted className="h-8 text-[12.5px]">{i}</Pill>) : <Empty step={3}>No interests yet</Empty>}
          </div>
          <SectionLabel className="pt-4">Types wanted</SectionLabel>
          <div className="flex flex-wrap gap-[7px] pt-2">
            {p.opportunity_types.length ? p.opportunity_types.map((t) => <Pill key={t} className="h-8 text-[12.5px]">{TYPE_LABELS[t]} ✓</Pill>) : <Empty step={3}>None chosen</Empty>}
          </div>
          {(p.preferred_location || p.availability) && (
            <p className="pt-3 text-[13px] text-muted">
              {[labelOf(PREFERRED_LOCATIONS, p.preferred_location), labelOf(AVAILABILITY, p.availability)].filter(Boolean).join(" · ")}
            </p>
          )}
        </Card>

        <Card icon="section-goal" title="Goal & links" step={4} readOnly={p.is_demo}>
          {p.goal ? (
            <p className="rounded-r-lg border-l-[3px] border-brand bg-page px-3.5 py-2.5 text-[13px] text-body">&ldquo;{p.goal}&rdquo;</p>
          ) : (
            <Empty step={4}>No goal yet</Empty>
          )}
          <div className="pt-3.5">
            <Facts
              rows={(["linkedin", "github", "portfolio", "other"] as const).map((kind) => {
                const url = link(kind);
                const label = { linkedin: "LinkedIn", github: "GitHub", portfolio: "Portfolio", other: "Other link" }[kind];
                return [
                  label,
                  url ? (
                    <a href={url.startsWith("http") ? url : `https://${url}`} target="_blank" rel="noopener noreferrer" className="truncate hover:text-brand">
                      {url.replace(/^https?:\/\//, "")}
                    </a>
                  ) : (
                    <span className="font-normal">
                      not added{!p.is_demo && (
                        <>
                          {" — "}
                          <Link href={edit(4)} className="text-[13px] font-bold text-brand">
                            add
                          </Link>
                        </>
                      )}
                    </span>
                  ),
                ];
              })}
            />
          </div>
        </Card>

        <Card icon="section-alerts" title="Alerts & consent" step={5} readOnly={p.is_demo}>
          <Facts
            rows={[
              [
                "Channels",
                <span key="c" className="flex flex-wrap items-center gap-1.5">
                  {[n.email_enabled && "Email ✓", n.telegram_enabled && "Telegram ✓"].filter(Boolean).join(" · ") || "None"}
                  <span className="rounded-full bg-line px-3 py-0.5 text-[13px] text-muted">SMS soon</span>
                </span>,
              ],
              ["Threshold", <span key="t" className="font-mono">≥ {n.threshold}% match</span>],
              ["Frequency", labelOf(FREQUENCIES, n.frequency).split(":")[0]],
              ["Quiet hours", n.quiet_start && n.quiet_end ? <span key="q" className="font-mono">{n.quiet_start.slice(0, 5)} – {n.quiet_end.slice(0, 5)}</span> : "None"],
              [
                "Consents",
                [p.consents.includes("terms_privacy") && "Terms ✓", p.consents.includes("agent_matching") && "Agent profile use ✓", p.consents.includes("ai_cv_processing") && "AI CV processing ✓"].filter(Boolean).join(" · ") || "None",
              ],
            ]}
          />
        </Card>
      </div>

      <section className="mt-4 flex flex-col gap-4 rounded-card border border-line bg-surface px-6 py-5 shadow-[0_1px_1.5px_rgb(30_17_62/0.05)] sm:flex-row sm:items-center">
        <div className="flex-1">
          <SectionLabel>Data &amp; privacy</SectionLabel>
          <p className="pt-2.5 text-sm text-body">
            Your CV file is stored in a private bucket only you can access, and deleted on request.{" "}
            <button type="button" onClick={download} className="text-[13px] font-bold text-brand">
              Export
            </button>{" "}
            · <span className="text-[13px] font-bold text-muted" title="Coming soon">Delete my account (soon)</span>
          </p>
        </div>
        <span className="flex shrink-0 items-center gap-1.5 self-start rounded-full bg-page px-3 py-1.5 text-xs font-bold text-body sm:self-center">
          <Image src="/icons/lock-muted.svg" alt="" width={13} height={13} />
          Only you can see this
        </span>
      </section>
    </div>
  );
}

/** First optional section that's empty (same order as the backend's completeness). */
function missingOptional(p: Me) {
  if (!p.links.length) return "Add a portfolio or GitHub link to reach 100%";
  if (!p.experiences.length && !p.certificates.length) return "Add an experience or certificate";
  if (!p.skills.some((s) => s.level)) return "Set a level for your skills";
  if (!p.languages.length) return "Add your languages";
  if (!p.institution) return "Add your institution";
  return "A few optional details are missing";
}

function missingOptionalStep(p: Me) {
  if (!p.links.length) return 4;
  if (!p.experiences.length && !p.certificates.length) return 2;
  if (!p.skills.some((s) => s.level)) return 3;
  if (!p.languages.length) return 1;
  return 2;
}

function Card({ icon, title, step, readOnly, children }: { icon: string; title: string; step: number; readOnly: boolean; children: ReactNode }) {
  return (
    <section className="flex flex-col rounded-card border border-line bg-surface px-6 py-5">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2.5 text-base font-bold text-ink">
          <span className="flex size-8 items-center justify-center rounded-[10px] bg-page">
            <Image src={`/icons/${icon}.svg`} alt="" width={17} height={17} />
          </span>
          {title}
        </h2>
        {!readOnly && (
          <ButtonLink href={edit(step)} variant="ghost" className="h-[34px] px-4 text-[13px]" aria-label={`Edit ${title}`}>
            Edit
          </ButtonLink>
        )}
      </div>
      <div className="pt-3.5">{children}</div>
    </section>
  );
}

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[minmax(96px,180px)_1fr] gap-x-3 gap-y-[9px] text-[14.5px]">
      {rows.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-muted">{label}</dt>
          <dd className="min-w-0 font-bold break-words text-ink">{value || <span className="font-normal text-muted">—</span>}</dd>
        </div>
      ))}
    </dl>
  );
}

function Empty({ step, children }: { step: number; children: ReactNode }) {
  return (
    <p className="text-sm text-muted">
      {children} —{" "}
      <Link href={edit(step)} className="font-bold text-brand">
        add
      </Link>
    </p>
  );
}

function ProfileSkeleton() {
  return (
    <Loading label="Loading your profile…" className="mx-auto max-w-[1112px]">
      <div className="flex justify-between">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-10 w-56 rounded-field" />
      </div>
      <div className="mt-4 flex items-center gap-5 rounded-card border border-line bg-surface px-7 py-6">
        <Skeleton className="size-[76px] rounded-full" />
        <div className="flex-1">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="mt-2 h-3.5 w-72" />
          <Skeleton className="mt-3 h-[26px] w-64 rounded-full" />
        </div>
        <Skeleton className="hidden h-12 w-[260px] md:block" />
      </div>
      <div className="grid gap-4 pt-[18px] md:grid-cols-2">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="rounded-card border border-line bg-surface px-6 py-5">
            <div className="flex items-center gap-2.5">
              <Skeleton className="size-8 rounded-[10px]" />
              <Skeleton className="h-5 w-32" />
            </div>
            {[0, 1, 2, 3].map((j) => <Skeleton key={j} className="mt-3.5 h-4 w-full" />)}
          </div>
        ))}
      </div>
    </Loading>
  );
}
