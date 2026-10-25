"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { Button, Spinner } from "@/components/ui/button";
import { Pill } from "@/components/ui/inputs";
import { Skeleton } from "@/components/ui/skeleton";
import { intlLocale, type Locale } from "@/i18n/config";
import { api, type Me, type Schemas } from "@/lib/api/client";

import { Choice, SettingRow, SettingsCard, Status, Toggle } from "./ui";
import { useSave } from "./use-save";

type Doc = Schemas["Document"];
type Consent = "agent_matching" | "ai_drafts" | "chat_history" | "anonymized_stats";

const CONSENTS: Consent[] = ["agent_matching", "ai_drafts", "chat_history", "anonymized_stats"];

export function PrivacyTab({ me }: { me: Me }) {
  const t = useTranslations("settings.privacy");
  const ts = useTranslations("settings");
  const locale = intlLocale(useLocale() as Locale);
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
      <SettingsCard label={t("data")}>
        {docs.isPending && <Skeleton className="h-[86px] w-full rounded-field" />}
        {docs.data?.length === 0 && (
          <p className="rounded-field border border-dashed border-line px-4 py-4 text-sm text-muted">
            {t("noCv")}{" "}
            {!ro && (
              <Link href="/onboarding?step=1" className="font-bold text-brand">
                {t("upload")}
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
                    {t("uploaded", {
                      kind: d.kind === "cv" ? t("yourCv") : d.kind,
                      date: new Date(d.created_at).toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric" }),
                    })}
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
                    onClick={() => window.confirm(t("confirmDelete", { name: d.file_name })) && remove.mutate(d.id)}
                  >
                    {remove.isPending && remove.variables === d.id && <Spinner />} {t("deleteFile")}
                  </Button>
                )}
              </div>
            );
          })}
        </div>
        <Status text={remove.isError ? t("deleteError", { error: remove.error.message }) : null} error />

        <div className="mt-3 border-t border-line">
          <SettingRow title={t("export")} description={t("exportHint")}>
            <Button variant="outline" className="h-10 text-sm" onClick={exportAll} disabled={exporting}>
              {exporting && <Spinner />} {t("download")}
            </Button>
          </SettingRow>
          <SettingRow title={t("retention")} description={t("retentionHint")} last>
            <Choice
              label={t("retention")}
              value={me.history_retention}
              disabled={ro}
              onChange={(v) => settings.mutate({ body: { history_retention: v }, optimistic: (m) => ({ ...m, history_retention: v }) })}
              options={[
                { value: "12_months", label: t("months12") },
                { value: "never", label: t("never") },
              ]}
            />
          </SettingRow>
        </div>
      </SettingsCard>

      <SettingsCard label={t("consents")}>
        {CONSENTS.map((c, i) => (
          <SettingRow key={c} title={t(`consent.${c}`)} description={t(`consent.${c}_hint`)} last={i === CONSENTS.length - 1}>
            <Toggle label={t(`consent.${c}`)} checked={me.consents.includes(c)} onChange={(v) => setConsent(c, v)} disabled={ro} />
          </SettingRow>
        ))}
        {!me.consents.includes("agent_matching") && (
          <p className="pt-2 text-xs text-warning">{t("matchingOff")}</p>
        )}
      </SettingsCard>

      <SettingsCard label={t("thirdParties")}>
        <SettingRow title={t("sources")} description={t("sourcesHint")}>
          <Link href="/settings?tab=agent" className="px-2 text-sm font-bold text-body hover:text-ink">
            {t("manage")}
          </Link>
        </SettingRow>
        <SettingRow title={t("provider")} description={t("providerHint")} />
        <SettingRow title={t("forms")} description={t("formsHint")} last />
      </SettingsCard>
      <Status text={consents.isError || settings.isError ? ts("saveError", { error: (consents.error ?? settings.error)?.message ?? "" }) : null} error />
    </>
  );
}
