"use client";

import Image from "next/image";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/field";
import { Select } from "@/components/ui/inputs";
import type { Me } from "@/lib/api/client";
import { FREQUENCIES } from "@/lib/onboarding/options";

import { Badge, Choice, SettingRow, SettingsCard, Status, Toggle } from "./ui";
import { useSave } from "./use-save";

type N = Me["notifications"];
type Rule = "rule_new_match" | "rule_deadline_reminders" | "rule_application_updates" | "rule_weekly_digest" | "rule_profile_tips";

const RULES: { key: Rule; title: string; description: string }[] = [
  { key: "rule_new_match", title: "New strong match", description: "As soon as an opportunity scores above your threshold" },
  { key: "rule_deadline_reminders", title: "Deadline reminders", description: "3 days before a saved opportunity closes" },
  { key: "rule_application_updates", title: "Application updates", description: "Status changes, receipts and organizer replies" },
  { key: "rule_weekly_digest", title: "Weekly scan digest", description: "One summary email on Monday morning" },
  { key: "rule_profile_tips", title: "Profile tips", description: "Suggestions to improve matching (at most once a week)" },
];

export function NotificationsTab({ me }: { me: Me }) {
  const n = me.notifications;
  const ro = me.is_demo;
  const save = useSave("/me/onboarding/alerts");
  const [channelError, setChannelError] = useState<string | null>(null);

  const set = (patch: Partial<N>) => save.mutate({ body: patch, optimistic: (m) => ({ ...m, notifications: { ...m.notifications, ...patch } }) });

  function setChannel(key: "email_enabled" | "telegram_enabled", on: boolean) {
    const other = key === "email_enabled" ? n.telegram_enabled : n.email_enabled;
    if (!on && !other) return setChannelError("Keep at least one channel on so alerts can reach you.");
    setChannelError(null);
    set({ [key]: on });
  }

  return (
    <>
      <SettingsCard label="Channels">
        <SettingRow title="Email" description={`${me.email} · alerts arrive here`}>
          <Toggle label="Email alerts" checked={n.email_enabled} onChange={(v) => setChannel("email_enabled", v)} disabled={ro} />
        </SettingRow>
        <SettingRow title="Telegram" description={n.telegram_linked ? "Connected · fastest for instant alerts" : "Not connected yet — linking your Telegram arrives with alerts"}>
          <Toggle label="Telegram alerts" checked={n.telegram_enabled} onChange={(v) => setChannel("telegram_enabled", v)} disabled={ro} />
        </SettingRow>
        <SettingRow title="SMS" description="Algerian numbers, planned for launch">
          <Badge>Soon</Badge>
        </SettingRow>
        <SettingRow title="In-app bell" description="Always on — the notifications panel in the header" last>
          <span className="text-xs text-muted">always on</span>
        </SettingRow>
        <Status text={channelError} error />
      </SettingsCard>

      <SettingsCard label="Alert rules">
        <div className="pt-1">
          {RULES.map((r) => (
            <SettingRow key={r.key} boxed title={r.title} description={r.key === "rule_new_match" ? `${r.description} (≥ ${n.threshold}%)` : r.description}>
              {r.key === "rule_new_match" && (
                <Choice
                  label="Match threshold"
                  value={n.threshold >= 85 ? "85" : "70"}
                  disabled={ro}
                  onChange={(v) => set({ threshold: Number(v) })}
                  options={[
                    { value: "70", label: <span className="font-mono">≥ 70%</span> },
                    { value: "85", label: <span className="font-mono">≥ 85%</span> },
                  ]}
                />
              )}
              <Toggle label={r.title} checked={n[r.key]} onChange={(v) => set({ [r.key]: v })} disabled={ro} />
            </SettingRow>
          ))}
        </div>
        <p className="pt-1 text-xs text-muted">Alerts start once matching launches; your choices are saved now.</p>
      </SettingsCard>

      <SettingsCard label="Quiet hours & frequency">
        <QuietHours n={n} readOnly={ro} onSave={set} />
        <SettingRow title="Frequency" description="How often match alerts are sent">
          <Select value={n.frequency} disabled={ro} onChange={(e) => set({ frequency: e.target.value as N["frequency"] })} aria-label="Alert frequency" className="w-auto min-w-64">
            {FREQUENCIES.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </Select>
        </SettingRow>
        <SettingRow title="Bundle non-urgent alerts" description="Combine alerts into 1–2 batches instead of one message each">
          <Toggle label="Bundle non-urgent alerts" checked={n.bundle_non_urgent} onChange={(v) => set({ bundle_non_urgent: v })} disabled={ro} />
        </SettingRow>
        <SettingRow title="Test alert" description="Send a sample message to check your channels" last>
          <Button variant="outline" className="h-10 text-sm" disabled title="Available when alerts launch">
            Send test · soon
          </Button>
        </SettingRow>
        <p className="mt-2 flex items-center justify-center gap-1.5 rounded-field bg-page px-3 py-2 text-xs font-bold text-body">
          <Image src="/icons/lock-muted.svg" alt="" width={12} height={12} />
          Alerts are about your opportunities only — never marketing
        </p>
      </SettingsCard>
      <Status text={save.isError ? `Couldn't save: ${save.error.message}` : null} error />
    </>
  );
}

function QuietHours({ n, readOnly, onSave }: { n: N; readOnly: boolean; onSave: (patch: Partial<N> & { clear_quiet_hours?: boolean }) => void }) {
  const on = Boolean(n.quiet_start && n.quiet_end);
  const [start, setStart] = useState(n.quiet_start?.slice(0, 5) ?? "22:00");
  const [end, setEnd] = useState(n.quiet_end?.slice(0, 5) ?? "07:00");
  const commit = (s: string, e: string) => s && e && onSave({ quiet_start: s, quiet_end: e });

  return (
    <SettingRow title="Quiet hours" description="Nothing arrives in this window">
      {on && (
        <span className="flex items-center gap-1.5">
          <Input type="time" value={start} disabled={readOnly} aria-label="Quiet hours start" className="h-9 w-[110px] font-mono text-sm" onChange={(e) => setStart(e.target.value)} onBlur={() => commit(start, end)} />
          <span className="text-muted">–</span>
          <Input type="time" value={end} disabled={readOnly} aria-label="Quiet hours end" className="h-9 w-[110px] font-mono text-sm" onChange={(e) => setEnd(e.target.value)} onBlur={() => commit(start, end)} />
        </span>
      )}
      <Choice
        label="Quiet hours"
        value={on ? "on" : "off"}
        disabled={readOnly}
        onChange={(v) =>
          v === "off"
            ? onSave({ quiet_start: null, quiet_end: null, clear_quiet_hours: true })
            : onSave({ quiet_start: start, quiet_end: end })
        }
        options={[
          { value: "on", label: "On" },
          { value: "off", label: "Off" },
        ]}
      />
    </SettingRow>
  );
}
