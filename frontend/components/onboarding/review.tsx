"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Pill, SectionLabel } from "@/components/ui/inputs";
import { firstIncompleteStep, isComplete } from "@/lib/onboarding/status";
import { labelOf, useOptions } from "@/lib/onboarding/options";

import { useWizard } from "./frame";
import { MissingList } from "./missing";

/** Profile review: "Start my agent" once setup is complete, otherwise what's missing + Continue setup. */
export function Review() {
  const t = useTranslations("onboarding.review");
  const ta = useTranslations("onboarding.alerts");
  const o = useOptions();
  const { me, goTo } = useWizard();
  const router = useRouter();

  const initials = (me.full_name || me.email).split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  const headline = [
    [me.current_year && labelOf(o.CURRENT_YEARS, me.current_year), me.field_of_study].filter(Boolean).join(" · "),
    [me.institution, o.wilayaLabel(me.wilaya)].filter(Boolean).join(", "),
  ].filter(Boolean).join(" · ");

  const n = me.notifications;
  const channels = [n.email_enabled && ta("email"), n.telegram_enabled && ta("telegram")].filter(Boolean).join(" + ");
  const frequency = labelOf(o.FREQUENCIES, n.frequency).split(/\s*[:：]/)[0];
  const quiet = n.quiet_start && n.quiet_end ? ` · ${t("quiet", { start: n.quiet_start.slice(0, 5), end: n.quiet_end.slice(0, 5) })}` : "";

  // The scan screen starts the agent and then lands on the dashboard.
  const start = () => router.push("/scan");
  const complete = isComplete(me);

  return (
    <div className="rounded-card border border-line bg-surface p-5 shadow-[0_1px_1.5px_rgb(30_17_62/0.05)] sm:p-9">
      <div className="flex items-center gap-4">
        <div className="flex size-16 shrink-0 items-center justify-center rounded-full bg-brand-soft text-[22px] font-bold text-brand-strong">{initials}</div>
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-2xl leading-tight font-bold tracking-[-0.5px] text-ink sm:text-[28px]">{me.full_name}</h1>
          {headline && <p className="text-sm text-body">{headline}</p>}
        </div>
        <span className={`hidden h-7 items-center rounded-full px-3 text-[13px] font-bold sm:flex ${complete ? "bg-success-tint text-success" : "bg-warning-tint text-warning"}`}>
          {me.is_demo ? t("demo") : complete ? t("ready") : t("incomplete")}
        </span>
      </div>

      <div className="grid gap-6 pt-[26px] sm:grid-cols-2">
        <Section title={t("about")}>
          <p className="text-sm leading-[26.6px] text-ink">
            {t("born", { year: me.birth_year ?? "—" })} · {o.nationalityLabel(me.nationality) || "—"} · {[o.wilayaLabel(me.wilaya), o.countryLabel(me.country)].filter(Boolean).join(", ")}
            <br />
            {me.languages.map((l) => `${l.language} (${labelOf(o.LANGUAGE_LEVELS, l.level)})`).join(", ") || t("noLanguages")}
          </p>
        </Section>
        <Section title={t("education")}>
          <p className="text-sm leading-[26.6px] text-ink">
            {[labelOf(o.EDUCATION_LEVELS, me.education_level), me.field_of_study].filter(Boolean).join(", ")}
            {me.graduation_year && ` · ${t("graduating", { year: me.graduation_year })}`}
            {me.gpa_value != null && ` · ${t("gpa", { value: me.gpa_value, scale: me.gpa_scale ?? 4 })}`}
            {(me.experiences.length > 0 || me.certificates.length > 0) && (
              <>
                <br />
                {t("counts", { experiences: me.experiences.length, certificates: me.certificates.length })}
              </>
            )}
          </p>
        </Section>
        <Section title={t("skills")}>
          <div className="flex flex-wrap gap-2.5">
            {me.skills.map((s) => (
              <Pill key={s.id ?? s.name} className="h-8">
                {s.name}
                {s.level && ` - ${labelOf(o.SKILL_LEVELS, s.level)}`}
              </Pill>
            ))}
          </div>
        </Section>
        <Section title={t("interests")}>
          <div className="flex flex-wrap gap-2.5">
            {me.interests.map((i) => <Pill key={i} muted className="h-8">{i}</Pill>)}
            {me.opportunity_types.map((type) => <Pill key={type} className="h-8">{o.typeLabel(type)}</Pill>)}
          </div>
          <p className="pt-2 text-xs text-muted">
            {[labelOf(o.PREFERRED_LOCATIONS, me.preferred_location), labelOf(o.AVAILABILITY, me.availability)].filter(Boolean).join(" · ")}
          </p>
        </Section>
        {me.goal && (
          <Section title={t("goal")} className="sm:col-span-2">
            <p className="rounded-e-lg border-s-[3px] border-brand bg-page px-3.5 py-2.5 text-[13px] text-body">&ldquo;{me.goal}&rdquo;</p>
          </Section>
        )}
        <Section title={t("alerts")}>
          <p className="text-sm leading-[26.6px] text-ink">
            {channels || t("noChannel")} · {frequency}
            <br />
            {t("threshold")} <strong className="font-mono">{n.threshold}%</strong>
            {quiet}
          </p>
        </Section>
        <Section title={t("links")}>
          {me.links.length ? (
            me.links.map((l) => (
              <a key={l.id ?? l.url} href={l.url.startsWith("http") ? l.url : `https://${l.url}`} target="_blank" rel="noreferrer" className="block truncate text-[13px] leading-[24.7px] font-bold text-brand hover:text-brand-strong">
                {l.url.replace(/^https?:\/\//, "")}
              </a>
            ))
          ) : (
            <p className="text-sm text-muted">{t("noLinks")}</p>
          )}
        </Section>
      </div>

      {!complete && (
        <Alert tone="info" className="mt-7">
          {me.onboarding.missing.length ? (
            <MissingList missing={me.onboarding.missing} />
          ) : (
            <p>{t("allFilled")}</p>
          )}
        </Alert>
      )}

      <div className="mt-7 flex flex-col gap-4 border-t border-line pt-6 sm:flex-row sm:items-center">
        <p className="flex-1 text-sm text-body">
          {complete ? (
            t.rich("editLater", {
              link: (c) => (
                <Link href="/profile" className="font-bold text-ink hover:text-brand">
                  {c}
                </Link>
              ),
            })
          ) : (
            t("finishFirst")
          )}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => goTo(1)}>
            <span className="inline-block rtl:-scale-x-100">&lt;</span> {t("editSection")}
          </Button>
          {complete ? (
            <Button size="md" className="bg-signal px-7 text-base text-on-signal hover:bg-signal-hover" onClick={start}>
              {t("start")} <span className="inline-block rtl:-scale-x-100">&gt;</span>
            </Button>
          ) : (
            <Button size="md" className="px-7 text-base" onClick={() => goTo(firstIncompleteStep(me))}>
              {t("continue")} <span className="inline-block rtl:-scale-x-100">&gt;</span>
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={className}>
      <SectionLabel className="pb-2.5">{title}</SectionLabel>
      {children}
    </section>
  );
}
