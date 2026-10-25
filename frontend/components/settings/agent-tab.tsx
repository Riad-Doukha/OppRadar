"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";

import type { Me } from "@/lib/api/client";
import { useOptions } from "@/lib/onboarding/options";
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

const GROUPS = ["universities", "companies", "events", "international"] as const satisfies readonly Group[];

/** Settings → Agent & sources. Saved now; the scan pipeline reads them once it ships. */
export function AgentTab({ me }: { me: Me }) {
  const t = useTranslations("settings.agent");
  const ts = useTranslations("settings");
  const { wilayaLabel } = useOptions();
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
        {t("intro")}
      </p>

      <SettingsCard label={t("scan")}>
        <SettingRow title={t("auto")} description={t("autoHint")}>
          <Toggle label={t("auto")} checked={a.auto_scan} onChange={(v) => set({ auto_scan: v })} disabled={ro} />
        </SettingRow>
        <SettingRow title={t("where")} description={me.wilaya ? t("whereWilaya", { wilaya: wilayaLabel(me.wilaya) }) : t("whereAll")}>
          <Choice
            label={t("where")}
            value={a.scope}
            disabled={ro}
            onChange={(v) => set({ scope: v })}
            options={[
              { value: "all_dz", label: t("allDz") },
              { value: "remote", label: t("remote") },
            ]}
          />
        </SettingRow>
        <SettingRow title={t("languages")} description={t("languagesHint")}>
          <div className="flex gap-1.5" role="group" aria-label={t("languages")}>
            {LANGS.map((l) => {
              const on = a.languages.includes(l.value);
              return (
                <button
                  key={l.value}
                  type="button"
                  aria-pressed={on}
                  disabled={ro || (on && a.languages.length === 1)}
                  title={on && a.languages.length === 1 ? t("keepOne") : undefined}
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
        <SettingRow title={t("threshold")} description={t("thresholdHint", { n: me.notifications.threshold })} last>
          <Choice
            label={t("threshold")}
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

      <SettingsCard label={t("own")}>
        <SettingRow title={t("eligibility")} description={t("eligibilityHint")}>
          <Toggle label={t("eligibilityLabel")} checked={a.check_eligibility} onChange={(v) => set({ check_eligibility: v })} disabled={ro} />
        </SettingRow>
        <SettingRow title={t("autoSave")} description={t("autoSaveHint")}>
          <Toggle label={t("autoSave")} checked={a.auto_save_high_matches} onChange={(v) => set({ auto_save_high_matches: v })} disabled={ro} />
        </SettingRow>
        <SettingRow title={t("drafts")} description={t("draftsHint")}>
          <Toggle label={t("drafts")} checked={a.draft_applications} onChange={(v) => set({ draft_applications: v })} disabled={ro} />
        </SettingRow>
        <SettingRow title={t("submit")} description={t("submitHint")} last>
          <Badge>{t("never")}</Badge>
        </SettingRow>
      </SettingsCard>

      <SettingsCard label={t("sources")}>
        <div className="flex flex-col gap-[9px] pt-0.5">
          {GROUPS.map((g) => {
            const on = a.source_groups[g];
            return (
              <div key={g} className={cn("flex items-center gap-3.5 rounded-field border px-4 py-3", on ? "border-brand-soft bg-page" : "border-line")}>
                <span className="flex size-[34px] shrink-0 items-center justify-center rounded-[10px] bg-page">
                  <Image src={`/icons/source-${g}.svg`} alt="" width={17} height={17} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[14.5px] text-ink">{t(`groups.${g}`)}</p>
                  <p className="text-xs text-muted">{t(`groups.${g}_hint`)}</p>
                </div>
                <Toggle label={t(`groups.${g}`)} checked={on} onChange={(v) => set({ source_groups: { ...a.source_groups, [g]: v } })} disabled={ro} />
              </div>
            );
          })}
        </div>
        <p className="pt-2.5 text-xs text-muted">{t("sourcesNote")}</p>
      </SettingsCard>
      <Status text={save.isError ? ts("saveError", { error: save.error.message }) : null} error />
    </>
  );
}
