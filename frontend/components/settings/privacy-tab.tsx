"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { Button, Spinner } from "@/components/ui/button";
import { Pill } from "@/components/ui/inputs";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Me, type Schemas } from "@/lib/api/client";

import { Choice, SettingRow, SettingsCard, Status, Toggle } from "./ui";
import { useSave } from "./use-save";

type Doc = Schemas["Document"];
type Consent = "agent_matching" | "ai_drafts" | "chat_history" | "anonymized_stats";

const CONSENTS: { key: Consent; title: string; description: string }[] = [
  {
    key: "agent_matching",
    title: "Use my profile to judge eligibility",
    description: "Your profile answers and CV fields are sent to the AI model to score opportunities. Turning this off turns matching off.",
  },
  { key: "ai_drafts", title: "AI-draft applications for me", description: "The agent may write drafts; you review every answer before anything is submitted. Nothing sends automatically." },
  { key: "chat_history", title: "Remember my chat history with the agent", description: "Kept 90 days, visible only to you · clear it anytime from Ask the agent" },
  { key: "anonymized_stats", title: "Improve OppRadar with anonymized data", description: "Anonymous match statistics only — never your name, CV or answers. Off by default." },
];

export function PrivacyTab({ me }: { me: Me }) {
  const ro = me.is_demo;
  const qc = useQueryClient();
  const consents = useSave("/me/onboarding/alerts");
  const settings = useSave("/me/settings");
  const docs = useQuery({ queryKey: ["documents"], queryFn: () => api<Doc[]>("/documents") });
  const [exporting, setExporting] = useState(false);

  const remove = useMutation({
    mutationFn: (id: string) => api(`/documents/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["me"] });
    },
  });

  function setConsent(key: Consent, on: boolean) {
    consents.mutate({
      body: { consents: { [key]: on } },
      optimistic: (m) => ({ ...m, consents: on ? [...new Set([...m.consents, key])] : m.consents.filter((c) => c !== key) }),
    });
  }

  async function exportAll() {
    setExporting(true);
    try {
      const [saved, documents] = await Promise.all([
        api<Schemas["MyOpportunityPage"]>("/me/opportunities?tab=saved&limit=100"),
        api<Doc[]>("/documents"),
      ]);
      const data = { exported_at: new Date().toISOString(), profile: me, saved_opportunities: saved.items, documents };
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      Object.assign(document.createElement("a"), { href: url, download: "oppradar-export.json" }).click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }

  return (
    <>
      <SettingsCard label="Your data">
        {docs.isPending && <Skeleton className="h-[86px] w-full rounded-field" />}
        {docs.data?.length === 0 && (
          <p className="rounded-field border border-dashed border-line px-4 py-4 text-sm text-muted">
            No CV uploaded.{" "}
            {!ro && (
              <Link href="/onboarding?step=1" className="font-bold text-brand">
                Upload one
              </Link>
            )}
          </p>
        )}
        <div className="flex flex-col gap-2.5">
          {docs.data?.map((d) => {
            const skills = ((d.extraction as { skills?: string[] } | null)?.skills ?? []).slice(0, 3);
            return (
              <div key={d.id} className="flex flex-col gap-3 rounded-field border border-line bg-page/60 px-4 py-3.5 sm:flex-row sm:items-center">
                <span className="w-fit rounded-md bg-brand px-2 py-[3px] font-mono text-xs font-bold text-white">PDF</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-ink">{d.file_name}</p>
                  <p className="text-[15px] text-ink">
                    {d.kind === "cv" ? "Your CV" : d.kind} · uploaded {new Date(d.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })} · private storage, deleted on request
                  </p>
                  {skills.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1.5">
                      {skills.map((s) => <Pill key={s} className="h-[22px] text-[11px]">{s} ✓</Pill>)}
                    </div>
                  )}
                </div>
                {!ro && (
                  <Button
                    variant="ghost"
                    className="h-9 text-sm"
                    disabled={remove.isPending}
                    onClick={() => window.confirm(`Delete ${d.file_name}? Your profile stays as it is.`) && remove.mutate(d.id)}
                  >
                    {remove.isPending && remove.variables === d.id && <Spinner />} Delete file
                  </Button>
                )}
              </div>
            );
          })}
        </div>
        <Status text={remove.isError ? `Couldn't delete: ${remove.error.message}` : null} error />

        <div className="mt-3 border-t border-line">
          <SettingRow title="Export everything" description="Profile, saved opportunities and uploaded-file details as one JSON file">
            <Button variant="outline" className="h-10 text-sm" onClick={exportAll} disabled={exporting}>
              {exporting && <Spinner />} Download
            </Button>
          </SettingRow>
          <SettingRow title="Application history retention" description="Auto-delete submitted application records after this period" last>
            <Choice
              label="Application history retention"
              value={me.history_retention}
              disabled={ro}
              onChange={(v) => settings.mutate({ body: { history_retention: v }, optimistic: (m) => ({ ...m, history_retention: v }) })}
              options={[
                { value: "12_months", label: "12 months" },
                { value: "never", label: "Never" },
              ]}
            />
          </SettingRow>
        </div>
      </SettingsCard>

      <SettingsCard label="AI processing — your consents">
        {CONSENTS.map((c, i) => (
          <SettingRow key={c.key} title={c.title} description={c.description} last={i === CONSENTS.length - 1}>
            <Toggle label={c.title} checked={me.consents.includes(c.key)} onChange={(v) => setConsent(c.key, v)} disabled={ro} />
          </SettingRow>
        ))}
        {!me.consents.includes("agent_matching") && (
          <p className="pt-2 text-xs text-warning">Matching is off: your agent won&apos;t score opportunities until you turn this back on.</p>
        )}
      </SettingsCard>

      <SettingsCard label="Third parties">
        <SettingRow title="Opportunity sources" description="Public pages from universities, organisations and event sites. No social-media scraping.">
          <Link href="/settings?tab=agent" className="px-2 text-sm font-bold text-body hover:text-ink">
            Manage
          </Link>
        </SettingRow>
        <SettingRow title="AI model provider" description="AI features (CV reading, matching, the agent) use the Google Gemini API, only for the features you turn on above." />
        <SettingRow title="Organizer forms" description="When the apply assistant launches, a form is filled only in your session. Organizers see their normal form and your answers." last />
      </SettingsCard>
      <Status text={consents.isError || settings.isError ? `Couldn't save: ${(consents.error ?? settings.error)?.message}` : null} error />
    </>
  );
}
