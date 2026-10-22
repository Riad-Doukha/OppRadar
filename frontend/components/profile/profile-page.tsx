"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { initialsOf } from "@/components/app/app-shell";
import { Alert } from "@/components/ui/alert";
import { Button, ButtonLink } from "@/components/ui/button";
import { Pill, SectionLabel } from "@/components/ui/inputs";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { api, type Me } from "@/lib/api/client";
import { labelOf, useOptions } from "@/lib/onboarding/options";
import { firstIncompleteStep, isComplete } from "@/lib/onboarding/status";
import { cn } from "@/lib/utils";

const edit = (step: number) => `/onboarding?step=${step}`;

/** "My profile" (Figma): the whole profile at a glance; each Edit opens that wizard step. */
export function ProfilePage() {
  const t = useTranslations("profile");
  const o = useOptions();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });

  if (me.isError) return <Alert>{t("loadError", { error: me.error.message })}</Alert>;
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
    [p.current_year && labelOf(o.CURRENT_YEARS, p.current_year), p.field_of_study].filter(Boolean).join(" · "),
    [p.institution, o.wilayaLabel(p.wilaya)].filter(Boolean).join(", "),
    p.graduation_year && t("graduating", { year: p.graduation_year }),
  ].filter(Boolean).join(" · ");

  const age = p.birth_year ? new Date().getFullYear() - p.birth_year : null;
  const n = p.notifications;
  const link = (kind: string) => p.links.find((l) => l.kind === kind)?.url;
  const tip = missingOptional(p);

  return (
    <div className="mx-auto max-w-[1112px]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-2xl font-bold tracking-[-0.5px] text-ink sm:text-[28px]">{t("title")}</h1>
        <div className="flex gap-2.5">
          <Button variant="ghost" className="h-10 text-sm" onClick={download}>
            {t("download")}
          </Button>
          {!p.is_demo && (
            <ButtonLink href={edit(1)} variant="outline" className="h-10 text-sm">
              {t("reupload")}
            </ButtonLink>
          )}
        </div>
      </div>

      {p.is_demo && (
        <Alert tone="info" className="mt-4">
          {t("demo")}
        </Alert>
      )}

      {/* Header card */}
      <section className="mt-4 flex flex-col gap-5 rounded-card border border-line bg-surface px-5 py-6 shadow-[0_1px_1.5px_rgb(30_17_62/0.05)] sm:px-7 md:flex-row md:items-center">
        <div className="flex size-[76px] shrink-0 items-center justify-center rounded-full bg-brand-soft text-[26px] font-bold text-brand-strong">{initialsOf(p.full_name || p.email)}</div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <p className="font-display text-[22px] font-bold text-ink">{p.full_name || p.email}</p>
            <span className={cn("flex h-7 items-center rounded-full px-3 text-[13px] font-bold", complete ? "bg-success-tint text-success" : "bg-warning-tint text-warning")}>
              {complete ? t("ready") : t("incomplete")}
            </span>
          </div>
          {headline && <p className="pt-1 text-[13px] text-muted">{headline}</p>}
          {p.skills.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-2.5">
              {p.skills.slice(0, 4).map((s) => <Pill key={s.id ?? s.name} className="h-[26px] text-xs">{s.name}</Pill>)}
              {p.skills.length > 4 && <Pill muted className="h-[26px] text-xs">{t("more", { count: p.skills.length - 4 })}</Pill>}
            </div>
          )}
        </div>
        <div className="w-full shrink-0 md:w-[260px]">
          <div className="flex items-baseline justify-between">
            <SectionLabel>{t("completeness")}</SectionLabel>
            <span className="font-mono text-base font-bold text-ink">{pct}%</span>
          </div>
          <div className="mt-1.5 h-[9px] overflow-hidden rounded-[5px] bg-line" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={t("completenessLabel")}>
            <div className="h-full rounded-[5px] bg-brand" style={{ width: `${pct}%` }} />
          </div>
          <p className="pt-2 text-xs text-muted">
            {!complete
              ? t.rich("missingRequired", {
                  link: (c) => (
                    <Link href={edit(firstIncompleteStep(p))} className="text-[13px] font-bold text-brand">
                      {c}
                    </Link>
                  ),
                })
              : pct < 100
                ? t.rich("addIt", {
                    tip: t(`tips.${tip}`),
                    link: (c) => (
                      <Link href={edit(missingOptionalStep(p))} className="text-[13px] font-bold text-brand">
                        {c}
                      </Link>
                    ),
                  })
                : t("complete")}
          </p>
        </div>
      </section>

      <div className="grid gap-4 pt-[18px] md:grid-cols-2">
        <Card icon="section-about" title={t("cards.about")} step={1} readOnly={p.is_demo}>
          <Facts
            rows={[
              [t("facts.fullName"), p.full_name],
              [t("facts.birthYear"), p.birth_year ? t("facts.age", { year: p.birth_year, age: age ?? 0 }) : null],
              [t("facts.nationality"), o.nationalityLabel(p.nationality)],
              [t("facts.location"), [o.wilayaLabel(p.wilaya), o.countryLabel(p.country)].filter(Boolean).join(", ")],
              [t("facts.languages"), p.languages.map((l) => `${l.language} ${labelOf(o.LANGUAGE_LEVELS, l.level)}`).join(" · ")],
            ]}
          />
        </Card>

        <Card icon="section-education" title={t("cards.education")} step={2} readOnly={p.is_demo}>
          <Facts
            rows={[
              [t("facts.level"), labelOf(o.EDUCATION_LEVELS, p.education_level)],
              [t("facts.field"), p.field_of_study],
              [t("facts.institution"), p.institution],
              [t("facts.year"), [p.current_year && labelOf(o.CURRENT_YEARS, p.current_year), p.graduation_year && t("graduating", { year: p.graduation_year })].filter(Boolean).join(" · ")],
              [t("facts.gpa"), p.gpa_value != null ? `${p.gpa_value} / ${p.gpa_scale}` : null],
            ]}
          />
        </Card>

        <Card icon="section-experience" title={t("cards.experience")} step={2} readOnly={p.is_demo}>
          {p.experiences.length + p.certificates.length === 0 ? (
            <Empty step={2}>{t("emptyExperience")}</Empty>
          ) : (
            <div className="flex flex-col gap-[9px]">
              {p.experiences.map((x) => (
                <div key={x.id} className="rounded-field border border-line px-3.5 py-[11px]">
                  <div className="flex flex-wrap items-center gap-[9px]">
                    <Pill className="h-[23px] text-[11px]">{labelOf(o.EXPERIENCE_KINDS, x.kind)}</Pill>
                    <span className="text-[14.5px] font-bold text-ink">{[x.title, x.organization].filter(Boolean).join(" — ")}</span>
                    {x.year && <span className="font-mono text-xs text-muted">{x.year}</span>}
                  </div>
                  {x.description && <p className="pt-1 text-[13px] text-body">{x.description}</p>}
                </div>
              ))}
              {p.certificates.map((c) => (
                <div key={c.id} className="rounded-field border border-line bg-raised px-3.5 py-[11px]">
                  <p className="text-[14.5px] font-bold text-body">{[c.title, c.issuer].filter(Boolean).join(" — ")}</p>
                  <p className="text-[13px] text-body">
                    {t("certificate")}{c.year ? ` · ${c.year}` : ""}
                    {c.credential_url && (
                      <>
                        {" · "}
                        <a href={c.credential_url} target="_blank" rel="noopener noreferrer" className="font-bold text-brand">
                          {t("credential")} <span className="inline-block rtl:-scale-x-100">↗</span>
                        </a>
                      </>
                    )}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card icon="section-skills" title={t("cards.skills")} step={3} readOnly={p.is_demo}>
          <SectionLabel>{t("skills")}</SectionLabel>
          <div className="flex flex-wrap gap-[7px] pt-2">
            {p.skills.length ? p.skills.map((s) => <Pill key={s.id ?? s.name} className="h-8 text-[12.5px]">{s.name}{s.level && ` · ${labelOf(o.SKILL_LEVELS, s.level)}`}</Pill>) : <Empty step={3}>{t("noSkills")}</Empty>}
          </div>
          <SectionLabel className="pt-4">{t("interests")}</SectionLabel>
          <div className="flex flex-wrap gap-[7px] pt-2">
            {p.interests.length ? p.interests.map((i) => <Pill key={i} muted className="h-8 text-[12.5px]">{i}</Pill>) : <Empty step={3}>{t("noInterests")}</Empty>}
          </div>
          <SectionLabel className="pt-4">{t("types")}</SectionLabel>
          <div className="flex flex-wrap gap-[7px] pt-2">
            {p.opportunity_types.length ? p.opportunity_types.map((type) => <Pill key={type} className="h-8 text-[12.5px]">{o.typeLabel(type)} ✓</Pill>) : <Empty step={3}>{t("noTypes")}</Empty>}
          </div>
          {(p.preferred_location || p.availability) && (
            <p className="pt-3 text-[13px] text-muted">
              {[labelOf(o.PREFERRED_LOCATIONS, p.preferred_location), labelOf(o.AVAILABILITY, p.availability)].filter(Boolean).join(" · ")}
            </p>
          )}
        </Card>

        <Card icon="section-goal" title={t("cards.goal")} step={4} readOnly={p.is_demo}>
          {p.goal ? (
            <p className="rounded-e-lg border-s-[3px] border-brand bg-page px-3.5 py-2.5 text-[13px] text-body">&ldquo;{p.goal}&rdquo;</p>
          ) : (
            <Empty step={4}>{t("noGoal")}</Empty>
          )}
          <div className="pt-3.5">
            <Facts
              rows={(["linkedin", "github", "portfolio", "other"] as const).map((kind) => {
                const url = link(kind);
                return [
                  t(`links.${kind}`),
                  url ? (
                    <a href={url.startsWith("http") ? url : `https://${url}`} target="_blank" rel="noopener noreferrer" className="block truncate hover:text-brand">
                      {url.replace(/^https?:\/\//, "")}
                    </a>
                  ) : (
                    <span className="font-normal">
                      {t("notAdded")}
                      {!p.is_demo && (
                        <>
                          {" — "}
                          <Link href={edit(4)} className="text-[13px] font-bold text-brand">
                            {t("add")}
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

        <Card icon="section-alerts" title={t("cards.alerts")} step={5} readOnly={p.is_demo}>
          <Facts
            rows={[
              [
                t("facts.channels"),
                <span key="c" className="flex flex-wrap items-center gap-1.5">
                  {[n.email_enabled && t("email"), n.telegram_enabled && t("telegram")].filter(Boolean).join(" · ") || t("none")}
                  <span className="rounded-full bg-line px-3 py-0.5 text-[13px] text-muted">{t("smsSoon")}</span>
                </span>,
              ],
              [t("facts.threshold"), <span key="t" className="font-mono">{t("facts.thresholdValue", { n: n.threshold })}</span>],
              [t("facts.frequency"), labelOf(o.FREQUENCIES, n.frequency).split(/\s*[:：]/)[0]],
              [t("facts.quiet"), n.quiet_start && n.quiet_end ? <span key="q" className="font-mono" dir="ltr">{n.quiet_start.slice(0, 5)} – {n.quiet_end.slice(0, 5)}</span> : t("none")],
              [
                t("facts.consents"),
                [p.consents.includes("terms_privacy") && t("consent.terms"), p.consents.includes("agent_matching") && t("consent.matching"), p.consents.includes("ai_cv_processing") && t("consent.cv")].filter(Boolean).join(" · ") || t("none"),
              ],
            ]}
          />
        </Card>
      </div>

      <section className="mt-4 flex flex-col gap-4 rounded-card border border-line bg-surface px-6 py-5 shadow-[0_1px_1.5px_rgb(30_17_62/0.05)] sm:flex-row sm:items-center">
        <div className="flex-1">
          <SectionLabel>{t("privacy.title")}</SectionLabel>
          <p className="pt-2.5 text-sm text-body">
            {t("privacy.body")}{" "}
            <button type="button" onClick={download} className="text-[13px] font-bold text-brand">
              {t("privacy.export")}
            </button>{" "}
            ·{" "}
            <Link href="/settings" className="text-[13px] font-bold text-brand">
              {t("privacy.delete")}
            </Link>
          </p>
        </div>
        <span className="flex shrink-0 items-center gap-1.5 self-start rounded-full bg-page px-3 py-1.5 text-xs font-bold text-body sm:self-center">
          <Image src="/icons/lock-muted.svg" alt="" width={13} height={13} className="icon-adapt" />
          {t("privacy.only")}
        </span>
      </section>
    </div>
  );
}

/** First optional section that's empty (same order as the backend's completeness). */
function missingOptional(p: Me) {
  if (!p.links.length) return "links";
  if (!p.experiences.length && !p.certificates.length) return "experience";
  if (!p.skills.some((s) => s.level)) return "skillLevels";
  if (!p.languages.length) return "languages";
  if (!p.institution) return "institution";
  return "other";
}

function missingOptionalStep(p: Me) {
  if (!p.links.length) return 4;
  if (!p.experiences.length && !p.certificates.length) return 2;
  if (!p.skills.some((s) => s.level)) return 3;
  if (!p.languages.length) return 1;
  return 2;
}

function Card({ icon, title, step, readOnly, children }: { icon: string; title: string; step: number; readOnly: boolean; children: ReactNode }) {
  const t = useTranslations("profile");
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
          <ButtonLink href={edit(step)} variant="ghost" className="h-[34px] px-4 text-[13px]" aria-label={t("editCard", { title })}>
            {t("edit")}
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
  const t = useTranslations("profile");
  return (
    <p className="text-sm text-muted">
      {children} —{" "}
      <Link href={edit(step)} className="font-bold text-brand">
        {t("add")}
      </Link>
    </p>
  );
}

function ProfileSkeleton() {
  const t = useTranslations("profile");
  return (
    <Loading label={t("loading")} className="mx-auto max-w-[1112px]">
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
