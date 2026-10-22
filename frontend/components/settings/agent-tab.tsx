"use client";

import Image from "next/image";

import type { Me } from "@/lib/api/client";
import { cn } from "@/lib/utils";

import { Badge, Choice, SettingRow, SettingsCard, Status, Toggle } from "./ui";
import { useSave } from "./use-save";

type Agent = Me["agent_settings"];
type Group = keyof Agent["source_groups"];
type Lang = Agent["languages"][number];

const LANGS: { value: Lang; label: string }[] = [
  { value: "en", label: "EN" },
  { value: "fr", label: "FR" },
  { value: "ar", label: "AR" },
];

const GROUPS: { key: Group; title: string; description: string }[] = [
  { key: "universities", title: "University boards", description: "Announcements from Algerian universities and schools" },
  { key: "companies", title: "Companies & startups", description: "Internship and job pages of companies hiring students" },
  { key: "events", title: "Events & hackathons", description: "Hackathons, datathons, competitions and bootcamps" },
  { key: "international", title: "International", description: "Remote-friendly programmes and scholarships abroad" },
];

/** Settings → Agent & sources. Saved now; the scan pipeline reads them once it ships. */
export function AgentTab({ me }: { me: Me }) {
  const a = me.agent_settings;
  const ro = me.is_demo;
  const save = useSave("/me/settings");
  const set = (patch: Partial<Agent>) =>
    save.mutate({ body: { agent: patch }, optimistic: (m) => ({ ...m, agent_settings: { ...m.agent_settings, ...patch } }) });

  function toggleLanguage(lang: Lang) {
    const next = a.languages.includes(lang) ? a.languages.filter((l) => l !== lang) : [...a.languages, lang];
    if (next.length) set({ languages: next });
  }

  return (
    <>
      <p className="rounded-field border border-brand-soft bg-page px-4 py-3 text-[13px] text-body">
        Scanning starts when the matching agent goes live. Your choices here are saved now and applied from the first scan.
      </p>

      <SettingsCard label="Scan behavior">
        <SettingRow title="Automatic scans" description="Let the agent check sources on its own, several times a day">
          <Toggle label="Automatic scans" checked={a.auto_scan} onChange={(v) => set({ auto_scan: v })} disabled={ro} />
        </SettingRow>
        <SettingRow title="Where the agent looks" description={me.wilaya ? `${me.wilaya} first, then all 58 wilayas — or remote opportunities only` : "All 58 wilayas — or remote opportunities only"}>
          <Choice
            label="Where the agent looks"
            value={a.scope}
            disabled={ro}
            onChange={(v) => set({ scope: v })}
            options={[
              { value: "all_dz", label: "All DZ" },
              { value: "remote", label: "Remote" },
            ]}
          />
        </SettingRow>
        <SettingRow title="Languages to scan" description="Arabic, French and English listings are detected and merged">
          <div className="flex gap-1.5" role="group" aria-label="Languages to scan">
            {LANGS.map((l) => {
              const on = a.languages.includes(l.value);
              return (
                <button
                  key={l.value}
                  type="button"
                  aria-pressed={on}
                  disabled={ro || (on && a.languages.length === 1)}
                  title={on && a.languages.length === 1 ? "Keep at least one language" : undefined}
                  onClick={() => toggleLanguage(l.value)}
                  className={cn(
                    "flex h-[27px] items-center rounded-full px-3.5 text-xs font-bold disabled:cursor-not-allowed",
                    on ? "bg-brand-soft text-brand-strong" : "border border-line bg-surface text-muted",
                  )}
                >
                  {l.label}
                  {on && " ✓"}
                </button>
              );
            })}
          </div>
        </SettingRow>
        <SettingRow title="Auto-match threshold" description={`Only surface what scores above this — your alert rule is ≥ ${me.notifications.threshold}%`} last>
          <Choice
            label="Auto-match threshold"
            value={a.min_score >= 70 ? "70" : "55"}
            disabled={ro}
            onChange={(v) => set({ min_score: Number(v) })}
            options={[
              { value: "55", label: <span className="font-mono">≥ 55%</span> },
              { value: "70", label: <span className="font-mono">≥ 70%</span> },
            ]}
          />
        </SettingRow>
      </SettingsCard>

      <SettingsCard label="What the agent may do on its own">
        <SettingRow title="Check eligibility & explain matches" description="Runs when a new opportunity appears">
          <Toggle label="Check eligibility" checked={a.check_eligibility} onChange={(v) => set({ check_eligibility: v })} disabled={ro} />
        </SettingRow>
        <SettingRow title="Save high-match opportunities" description="≥ 85% is saved automatically so nothing expires unseen">
          <Toggle label="Save high-match opportunities" checked={a.auto_save_high_matches} onChange={(v) => set({ auto_save_high_matches: v })} disabled={ro} />
        </SettingRow>
        <SettingRow title="Draft applications" description="Pre-fills drafts you can review — but never submits anything without your press">
          <Toggle label="Draft applications" checked={a.draft_applications} onChange={(v) => set({ draft_applications: v })} disabled={ro} />
        </SettingRow>
        <SettingRow title="Submit on my behalf" description="Off permanently — submission always needs a human. This can't be enabled." last>
          <Badge>never allowed</Badge>
        </SettingRow>
      </SettingsCard>

      <SettingsCard label="Sources">
        <div className="flex flex-col gap-[9px] pt-0.5">
          {GROUPS.map((g) => {
            const on = a.source_groups[g.key];
            return (
              <div key={g.key} className={cn("flex items-center gap-3.5 rounded-field border px-4 py-3", on ? "border-brand-soft bg-page" : "border-line")}>
                <span className="flex size-[34px] shrink-0 items-center justify-center rounded-[10px] bg-page">
                  <Image src={`/icons/source-${g.key}.svg`} alt="" width={17} height={17} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[14.5px] text-ink">{g.title}</p>
                  <p className="text-xs text-muted">{g.description}</p>
                </div>
                <Toggle label={g.title} checked={on} onChange={(v) => set({ source_groups: { ...a.source_groups, [g.key]: v } })} disabled={ro} />
              </div>
            );
          })}
        </div>
        <p className="pt-2.5 text-xs text-muted">Sources are public pages only. The full source list appears here once scanning goes live.</p>
      </SettingsCard>
      <Status text={save.isError ? `Couldn't save: ${save.error.message}` : null} error />
    </>
  );
}
