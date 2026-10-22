"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { Select } from "@/components/ui/inputs";
import type { Me } from "@/lib/api/client";
import { useOptions } from "@/lib/onboarding/options";

import { Badge, Choice, SettingRow, SettingsCard, Status, Toggle } from "./ui";
import { useSave } from "./use-save";

type N = Me["notifications"];
type Rule = "rule_new_match" | "rule_deadline_reminders" | "rule_application_updates" | "rule_weekly_digest" | "rule_profile_tips";

const RULES: Rule[] = ["rule_new_match", "rule_deadline_reminders", "rule_application_updates", "rule_weekly_digest", "rule_profile_tips"];

export function NotificationsTab({ me }: { me: Me }) {
  const t = useTranslations("settings.notifications");
  const ts = useTranslations("settings");
  const { FREQUENCIES } = useOptions();
  const n = me.notifications;
  const ro = me.is_demo;
  const save = useSave("/me/onboarding/alerts");
  const [channelError, setChannelError] = useState<string | null>(null);

  const set = (patch: Partial<N>) => save.mutate({ body: patch, optimistic: (m) => ({ ...m, notifications: { ...m.notifications, ...patch } }) });

  function setChannel(key: "email_enabled" | "telegram_enabled", on: boolean) {
    const other = key === "email_enabled" ? n.telegram_enabled : n.email_enabled;
    if (!on && !other) return setChannelError(t("keepOne"));
    setChannelError(null);
    set({ [key]: on });
  }

  return (
    <>
      <SettingsCard label={t("channels")}>
        <SettingRow title={t("email")} description={t("emailHint", { email: me.email })}>
          <Toggle label={t("emailToggle")} checked={n.email_enabled} onChange={(v) => setChannel("email_enabled", v)} disabled={ro} />
        </SettingRow>
        <SettingRow title={t("telegram")} description={n.telegram_linked ? t("telegramLinked") : t("telegramNot")}>
          <Toggle label={t("telegramToggle")} checked={n.telegram_enabled} onChange={(v) => setChannel("telegram_enabled", v)} disabled={ro} />
        </SettingRow>
        <SettingRow title={t("sms")} description={t("smsHint")}>
          <Badge>{t("soonBadge")}</Badge>
        </SettingRow>
        <SettingRow title={t("bell")} description={t("bellHint")} last>
          <span className="text-xs text-muted">{t("alwaysOn")}</span>
        </SettingRow>
        <Status text={channelError} error />
      </SettingsCard>

      <SettingsCard label={t("rules")}>
        <div className="pt-1">
          {RULES.map((r) => (
            <SettingRow key={r} boxed title={t(`rule.${r}`)} description={r === "rule_new_match" ? t("withThreshold", { hint: t(`rule.${r}_hint`), n: n.threshold }) : t(`rule.${r}_hint`)}>
              {r === "rule_new_match" && (
                <Choice
                  label={t("matchThreshold")}
                  value={n.threshold >= 85 ? "85" : "70"}
                  disabled={ro}
                  onChange={(v) => set({ threshold: Number(v) })}
                  options={[
                    { value: "70", label: <span className="font-mono">≥ 70%</span> },
                    { value: "85", label: <span className="font-mono">≥ 85%</span> },
                  ]}
                />
              )}
              <Toggle label={t(`rule.${r}`)} checked={n[r]} onChange={(v) => set({ [r]: v })} disabled={ro} />
            </SettingRow>
          ))}
        </div>
        <p className="pt-1 text-xs text-muted">{t("rulesLater")}</p>
      </SettingsCard>

      <SettingsCard label={t("quietCard")}>
        <QuietHours n={n} readOnly={ro} onSave={set} />
        <SettingRow title={t("frequency")} description={t("frequencyHint")}>
          <Select value={n.frequency} disabled={ro} onChange={(e) => set({ frequency: e.target.value as N["frequency"] })} aria-label={t("frequencyLabel")} className="w-auto min-w-64">
            {FREQUENCIES.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </Select>
        </SettingRow>
        <SettingRow title={t("bundle")} description={t("bundleHint")}>
          <Toggle label={t("bundle")} checked={n.bundle_non_urgent} onChange={(v) => set({ bundle_non_urgent: v })} disabled={ro} />
        </SettingRow>
        <SettingRow title={t("test")} description={t("testHint")} last>
          <Button variant="outline" className="h-10 text-sm" disabled title={t("testSoonTitle")}>
            {t("testSoon")}
          </Button>
        </SettingRow>
        <p className="mt-2 flex items-center justify-center gap-1.5 rounded-field bg-page px-3 py-2 text-xs font-bold text-body">
          <Image src="/icons/lock-muted.svg" alt="" width={12} height={12} className="icon-adapt" />
          {t("noMarketing")}
        </p>
      </SettingsCard>
      <Status text={save.isError ? ts("saveError", { error: save.error.message }) : null} error />
    </>
  );
}

function QuietHours({ n, readOnly, onSave }: { n: N; readOnly: boolean; onSave: (patch: Partial<N> & { clear_quiet_hours?: boolean }) => void }) {
  const t = useTranslations("settings.notifications");
  const on = Boolean(n.quiet_start && n.quiet_end);
  const [start, setStart] = useState(n.quiet_start?.slice(0, 5) ?? "22:00");
  const [end, setEnd] = useState(n.quiet_end?.slice(0, 5) ?? "07:00");
  const commit = (s: string, e: string) => s && e && onSave({ quiet_start: s, quiet_end: e });

  return (
    <SettingRow title={t("quiet")} description={t("quietHint")}>
      {on && (
        <span className="flex items-center gap-1.5" dir="ltr">
          <Input type="time" value={start} disabled={readOnly} aria-label={t("quietStart")} className="h-9 w-[110px] font-mono text-sm" onChange={(e) => setStart(e.target.value)} onBlur={() => commit(start, end)} />
          <span className="text-muted">–</span>
          <Input type="time" value={end} disabled={readOnly} aria-label={t("quietEnd")} className="h-9 w-[110px] font-mono text-sm" onChange={(e) => setEnd(e.target.value)} onBlur={() => commit(start, end)} />
        </span>
      )}
      <Choice
        label={t("quiet")}
        value={on ? "on" : "off"}
        disabled={readOnly}
        onChange={(v) =>
          v === "off"
            ? onSave({ quiet_start: null, quiet_end: null, clear_quiet_hours: true })
            : onSave({ quiet_start: start, quiet_end: end })
        }
        options={[
          { value: "on", label: t("on") },
          { value: "off", label: t("off") },
        ]}
      />
    </SettingRow>
  );
}
