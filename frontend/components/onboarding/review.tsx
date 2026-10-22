"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Pill, SectionLabel } from "@/components/ui/inputs";
import { firstIncompleteStep, isComplete } from "@/lib/onboarding/status";
import { AVAILABILITY, CURRENT_YEARS, EDUCATION_LEVELS, FREQUENCIES, OPPORTUNITY_TYPES, PREFERRED_LOCATIONS, labelOf } from "@/lib/onboarding/options";

import { useWizard } from "./frame";
import { MissingList } from "./missing";

const ordinal = (n: number) => labelOf(CURRENT_YEARS, n).replace(" year", "-year");

/** Profile review: "Start my agent" once setup is complete, otherwise what's missing + Continue setup. */
export function Review() {
  const { me, goTo } = useWizard();
  const router = useRouter();

  const initials = (me.full_name || me.email).split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  const headline = [
    [me.current_year && ordinal(me.current_year), me.field_of_study].filter(Boolean).join(" "),
    [me.institution, me.wilaya].filter(Boolean).join(", "),
  ].filter(Boolean).join(" · ");

  const n = me.notifications;
  const channels = [n.email_enabled && "Email", n.telegram_enabled && "Telegram"].filter(Boolean).join(" + ");
  const frequency = labelOf(FREQUENCIES, n.frequency).split(":")[0];
  const quiet = n.quiet_start && n.quiet_end ? ` · Quiet ${n.quiet_start.slice(0, 5)} to ${n.quiet_end.slice(0, 5)}` : "";

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
        <span className={`hidden h-7 items-center rounded-full px-3 text-[13px] font-bold sm:flex ${complete ? "bg-[#ecfdf5] text-success" : "bg-[#fffbeb] text-warning"}`}>
          {me.is_demo ? "Demo" : complete ? "Ready" : "Incomplete"}
        </span>
      </div>

      <div className="grid gap-6 pt-[26px] sm:grid-cols-2">
        <Section title="About">
          <p className="text-sm leading-[26.6px] text-ink">
            Born {me.birth_year ?? "—"} · {me.nationality ?? "—"} · {[me.wilaya, me.country].filter(Boolean).join(", ")}
            <br />
            {me.languages.map((l) => `${l.language} (${l.level})`).join(", ") || "No languages yet"}
          </p>
        </Section>
        <Section title="Education">
          <p className="text-sm leading-[26.6px] text-ink">
            {[labelOf(EDUCATION_LEVELS, me.education_level), me.field_of_study].filter(Boolean).join(", ")}
            {me.graduation_year && ` · graduating ${me.graduation_year}`}
            {me.gpa_value != null && ` · GPA ${me.gpa_value}/${me.gpa_scale}`}
            {(me.experiences.length > 0 || me.certificates.length > 0) && (
              <>
                <br />
                {me.experiences.length} experience{me.experiences.length === 1 ? "" : "s"} · {me.certificates.length} certificate{me.certificates.length === 1 ? "" : "s"}
              </>
            )}
          </p>
        </Section>
        <Section title="Skills">
          <div className="flex flex-wrap gap-2.5">
            {me.skills.map((s) => (
              <Pill key={s.id ?? s.name} className="h-8">
                {s.name}
                {s.level && ` - ${s.level[0].toUpperCase()}${s.level.slice(1)}`}
              </Pill>
            ))}
          </div>
        </Section>
        <Section title="Interests & types wanted">
          <div className="flex flex-wrap gap-2.5">
            {me.interests.map((i) => <Pill key={i} muted className="h-8">{i}</Pill>)}
            {me.opportunity_types.map((t) => <Pill key={t} className="h-8">{labelOf(OPPORTUNITY_TYPES, t) || t}</Pill>)}
          </div>
          <p className="pt-2 text-xs text-muted">
            {[labelOf(PREFERRED_LOCATIONS, me.preferred_location), labelOf(AVAILABILITY, me.availability)].filter(Boolean).join(" · ")}
          </p>
        </Section>
        {me.goal && (
          <Section title="Goal" className="sm:col-span-2">
            <p className="rounded-r-lg border-l-[3px] border-brand bg-page px-3.5 py-2.5 text-[13px] text-body">&ldquo;{me.goal}&rdquo;</p>
          </Section>
        )}
        <Section title="Alerts">
          <p className="text-sm leading-[26.6px] text-ink">
            {channels || "No channel"} · {frequency}
            <br />
            Threshold <strong className="font-mono">{n.threshold}%</strong>
            {quiet}
          </p>
        </Section>
        <Section title="Links">
          {me.links.length ? (
            me.links.map((l) => (
              <a key={l.id ?? l.url} href={l.url.startsWith("http") ? l.url : `https://${l.url}`} target="_blank" rel="noreferrer" className="block truncate text-[13px] leading-[24.7px] font-bold text-brand hover:text-brand-strong">
                {l.url.replace(/^https?:\/\//, "")}
              </a>
            ))
          ) : (
            <p className="text-sm text-muted">No links</p>
          )}
        </Section>
      </div>

      {!complete && (
        <Alert tone="info" className="mt-7">
          {me.onboarding.missing.length ? (
            <MissingList missing={me.onboarding.missing} />
          ) : (
            <p>Everything required is filled in — press Finish setup on step 5 to complete it.</p>
          )}
        </Alert>
      )}

      <div className="mt-7 flex flex-col gap-4 border-t border-line pt-6 sm:flex-row sm:items-center">
        <p className="flex-1 text-sm text-body">
          {complete ? (
            <>
              You can edit all of this later in <Link href="/profile" className="font-bold text-ink hover:text-brand">My profile</Link>.
            </>
          ) : (
            "Finish the setup so your agent can start matching you."
          )}
        </p>
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => goTo(1)}>
            &lt; Edit a section
          </Button>
          {complete ? (
            <Button size="md" className="bg-signal px-7 text-base text-ink hover:bg-[#eef03c]" onClick={start}>
              Start my agent &gt;
            </Button>
          ) : (
            <Button size="md" className="px-7 text-base" onClick={() => goTo(firstIncompleteStep(me))}>
              Continue setup &gt;
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
