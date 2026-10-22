"use client";

import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Alert } from "@/components/ui/alert";
import { Button, Spinner } from "@/components/ui/button";
import { Pill, SectionLabel } from "@/components/ui/inputs";
import { ApiError, api } from "@/lib/api/client";
import { AVAILABILITY, CURRENT_YEARS, EDUCATION_LEVELS, FREQUENCIES, OPPORTUNITY_TYPES, PREFERRED_LOCATIONS, labelOf } from "@/lib/onboarding/options";

import { useWizard } from "./frame";

const ordinal = (n: number) => labelOf(CURRENT_YEARS, n).replace(" year", "-year");

/** "SETUP COMPLETE: Review your profile" + Start my agent. */
export function Review() {
  const { me, goTo } = useWizard();
  const router = useRouter();
  const [starting, setStarting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const initials = (me.full_name || me.email).split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  const headline = [
    [me.current_year && ordinal(me.current_year), me.field_of_study].filter(Boolean).join(" "),
    [me.institution, me.wilaya].filter(Boolean).join(", "),
  ].filter(Boolean).join(" · ");

  const n = me.notifications;
  const channels = [n.email_enabled && "Email", n.telegram_enabled && "Telegram"].filter(Boolean).join(" + ");
  const frequency = labelOf(FREQUENCIES, n.frequency).split(":")[0];
  const quiet = n.quiet_start && n.quiet_end ? ` · Quiet ${n.quiet_start.slice(0, 5)} to ${n.quiet_end.slice(0, 5)}` : "";

  async function start() {
    setStarting(true);
    setNotice(null);
    try {
      await api("/me/agent/start", { method: "POST" });
      router.push("/dashboard");
    } catch (e) {
      // 501 until the matching phase ships: the profile is saved, the agent isn't live yet.
      if (e instanceof ApiError && e.status === 501) setNotice("Your profile is saved and ready. The matching agent isn't live yet — we'll start it as soon as it is.");
      else setNotice("We couldn't start your agent. Please try again.");
    }
    setStarting(false);
  }

  return (
    <div className="rounded-card border border-line bg-surface p-5 shadow-[0_1px_1.5px_rgb(30_17_62/0.05)] sm:p-9">
      <div className="flex items-center gap-4">
        <div className="flex size-16 shrink-0 items-center justify-center rounded-full bg-brand-soft text-[22px] font-bold text-brand-strong">{initials}</div>
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-2xl leading-tight font-bold tracking-[-0.5px] text-ink sm:text-[28px]">{me.full_name}</h1>
          {headline && <p className="text-sm text-body">{headline}</p>}
        </div>
        <span className="hidden h-7 items-center rounded-full bg-[#ecfdf5] px-3 text-[13px] font-bold text-success sm:flex">{me.is_demo ? "Demo" : "Ready"}</span>
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

      {notice && <Alert tone="info" className="mt-6">{notice}</Alert>}

      <div className="mt-7 flex flex-col gap-4 border-t border-line pt-6 sm:flex-row sm:items-center">
        <p className="flex-1 text-sm text-body">
          You can edit all of this later in <strong>My profile</strong>.
        </p>
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => goTo(1)}>
            &lt; Edit a section
          </Button>
          <Button size="md" className="bg-signal px-7 text-base text-ink hover:bg-[#eef03c]" onClick={start} disabled={starting}>
            {starting && <Spinner />}
            Start my agent &gt;
          </Button>
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
