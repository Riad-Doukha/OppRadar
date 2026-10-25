"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, Input } from "@/components/ui/field";
import { ChoiceCard, SectionLabel, Select } from "@/components/ui/inputs";
import { ApiError, api, type Me, type Schemas } from "@/lib/api/client";
import { useOptions } from "@/lib/onboarding/options";
import { useAutosave } from "@/lib/onboarding/save-status";
import { cn } from "@/lib/utils";

import { Row, StepFrame, useWizard } from "./frame";
import { MissingList } from "./missing";

type Frequency = NonNullable<Schemas["AlertsStep"]["frequency"]>;
const hhmm = (t: string | null | undefined) => (t ? t.slice(0, 5) : "");

export function StepAlerts() {
  const t = useTranslations("onboarding.alerts");
  const tr = useTranslations("onboarding");
  const { FREQUENCIES } = useOptions();
  const { me, goTo } = useWizard();
  const qc = useQueryClient();
  const n = me.notifications;
  const documents = useQuery({ queryKey: ["documents"], queryFn: () => api<unknown[]>("/documents") });
  const cvUploaded = (documents.data?.length ?? 0) > 0;

  const [email, setEmail] = useState(n.email_enabled);
  const [telegram, setTelegram] = useState(n.telegram_enabled);
  const [threshold, setThreshold] = useState(n.threshold);
  const [frequency, setFrequency] = useState<Frequency>(n.frequency);
  const [quietStart, setQuietStart] = useState(hhmm(n.quiet_start));
  const [quietEnd, setQuietEnd] = useState(hhmm(n.quiet_end));
  const [consents, setConsents] = useState(() => ({
    terms_privacy: me.consents.includes("terms_privacy"),
    agent_matching: me.consents.includes("agent_matching"),
    ai_cv_processing: me.consents.includes("ai_cv_processing"),
  }));
  const [missing, setMissing] = useState<string[] | null>(null);

  const body = useMemo(() => {
    // Both times, or clear both; a half-filled pair isn't sent yet.
    const quiet = quietStart && quietEnd ? { quiet_start: quietStart, quiet_end: quietEnd } : !quietStart && !quietEnd ? { clear_quiet_hours: true } : {};
    return { email_enabled: email, telegram_enabled: telegram, threshold, frequency, ...quiet, consents };
  }, [email, telegram, threshold, frequency, quietStart, quietEnd, consents]);
  const { flush } = useAutosave("/me/onboarding/alerts", body, { enabled: !me.is_demo });

  const errors = {
    channel: email || telegram ? null : t("needChannel"),
    quiet: Boolean(quietStart) === Boolean(quietEnd) ? null : t("quietError"),
    terms_privacy: consents.terms_privacy ? null : tr("required"),
    agent_matching: consents.agent_matching ? null : t("matchingRequired"),
    ai_cv_processing: !cvUploaded || consents.ai_cv_processing ? null : t("cvRequired"),
  };

  async function finish() {
    setMissing(null);
    if (me.is_demo) return goTo("review");
    try {
      const done = await api<Me>("/me/onboarding/complete", { method: "POST" });
      qc.setQueryData(["me"], done);
      goTo("review");
    } catch (e) {
      const detail = e instanceof ApiError ? (e.detail as { missing?: string[] }) : null;
      setMissing(detail?.missing ?? ["unknown"]);
    }
  }

  const pct = ((threshold - 50) / 50) * 100;
  const consent = (k: keyof typeof consents) => (v: React.ChangeEvent<HTMLInputElement>) => setConsents((s) => ({ ...s, [k]: v.target.checked }));

  return (
    <StepFrame step={5} errors={errors} flush={flush} onFinish={finish}>
      {(show) => (
        <>
          {missing && (
            <Alert className="mb-5">
              <MissingList missing={missing} />
            </Alert>
          )}

          <fieldset>
            <legend className="text-[13px] font-bold text-ink">{t("channels")}</legend>
            <div className="flex flex-col gap-2.5 pt-1.5">
              <ChoiceCard checked={email} onChange={setEmail} className="p-4">
                <span className="min-w-0 flex-1">
                  <span className="block text-[15px] font-bold text-ink">{t("email")}</span>
                  <span className="block truncate text-sm text-body">{me.email}</span>
                </span>
                {email && <span className="flex h-7 items-center rounded-full bg-success-tint px-3 text-[13px] font-bold text-success">{t("on")}</span>}
              </ChoiceCard>
              <ChoiceCard checked={telegram} onChange={setTelegram} className="p-4">
                <span className="min-w-0 flex-1">
                  <span className="block text-[15px] font-bold text-ink">{t("telegram")}</span>
                  <span className="block text-sm text-body">{t("telegramBody")}</span>
                </span>
                <Button type="button" variant="outline" className="h-9 px-4 text-[13px]" disabled title={t("telegramSoon")}>
                  {n.telegram_linked ? t("connected") : t("connect")}
                </Button>
              </ChoiceCard>
            </div>
            {show && errors.channel && <p className="pt-1.5 text-xs text-danger">{errors.channel}</p>}
            {telegram && !n.telegram_linked && <p className="pt-1.5 text-xs text-muted">{t("telegramLater")}</p>}
          </fieldset>

          <div className="pt-[22px]">
            <label htmlFor="threshold" className="text-[13px] font-bold text-ink">
              {t("threshold")}
            </label>
            <p className="pt-1 text-xs text-muted">{t("thresholdHint")}</p>
            <div className="flex items-center gap-4 pt-3">
              <input
                id="threshold"
                type="range"
                min={50}
                max={100}
                step={5}
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className="range-brand h-2 flex-1 cursor-pointer"
                style={{ "--fill": `${pct}%` } as React.CSSProperties}
              />
              <span className="flex h-8 items-center rounded-full bg-brand-soft px-3 font-mono text-sm font-semibold text-brand-strong">{threshold}%</span>
            </div>
            <div className="flex justify-between pt-2 text-xs text-muted">
              <span>50%</span>
              <span>{t("default")}</span>
              <span>100%</span>
            </div>
          </div>

          <Row className="pt-[22px]">
            <Field label={t("frequency")}>
              {(p) => (
                <Select {...p} value={frequency} onChange={(e) => setFrequency(e.target.value as Frequency)}>
                  {FREQUENCIES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </Select>
              )}
            </Field>
            <Field label={t("quiet")} error={show ? errors.quiet ?? undefined : undefined} hint={t("quietHint")}>
              {(p) => (
                <div className="flex items-center gap-2">
                  <Input {...p} type="time" value={quietStart} onChange={(e) => setQuietStart(e.target.value)} aria-label={t("quietStart")} />
                  <span className="text-sm text-muted">{t("to")}</span>
                  <Input type="time" value={quietEnd} onChange={(e) => setQuietEnd(e.target.value)} aria-label={t("quietEnd")} invalid={p.invalid} />
                </div>
              )}
            </Field>
          </Row>

          <SectionLabel className="pt-7">{t("consent")}</SectionLabel>
          <div className="flex flex-col gap-3 pt-2.5">
            <ConsentRow error={show ? errors.terms_privacy : null}>
              <Checkbox checked={consents.terms_privacy} onChange={consent("terms_privacy")}>
                <span className="text-sm text-ink">{t.rich("terms", {
                    terms: (c) => <Link href="/terms" target="_blank" className="font-bold underline underline-offset-2">{c}</Link>,
                    privacy: (c) => <Link href="/privacy" target="_blank" className="font-bold underline underline-offset-2">{c}</Link>,
                  })}</span>
              </Checkbox>
            </ConsentRow>
            <ConsentRow error={show ? errors.agent_matching : null}>
              <Checkbox checked={consents.agent_matching} onChange={consent("agent_matching")}>
                <span className="text-sm text-ink">{t("matching")}</span>
              </Checkbox>
            </ConsentRow>
            <ConsentRow error={show ? errors.ai_cv_processing : null}>
              <Checkbox checked={consents.ai_cv_processing} onChange={consent("ai_cv_processing")}>
                <span className="text-sm text-ink">
                  {t("cv")}
                  {!cvUploaded && <span className="text-muted"> {t("cvOnlyIf")}</span>}
                </span>
              </Checkbox>
            </ConsentRow>
          </div>
        </>
      )}
    </StepFrame>
  );
}

function ConsentRow({ error, children }: { error: string | null; children: React.ReactNode }) {
  return (
    <div className={cn(error && "rounded-md")}>
      {children}
      {error && <p className="pt-1 ps-7 text-xs text-danger">{error}</p>}
    </div>
  );
}
