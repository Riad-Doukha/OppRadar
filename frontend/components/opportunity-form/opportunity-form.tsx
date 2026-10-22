"use client";

import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button, Spinner } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Select, TagInput } from "@/components/ui/inputs";
import { LOCALES, LOCALE_NAMES } from "@/i18n/config";
import { useOptions, type OpportunityType } from "@/lib/onboarding/options";
import { TRUST_LEVELS, type Reviewed, type TrustLevel } from "@/lib/review";
import { cn } from "@/lib/utils";

const TYPES: OpportunityType[] = [
  "hackathon", "datathon", "competition", "scholarship", "internship", "fellowship",
  "job", "bootcamp", "research", "volunteer", "course", "grant", "other",
];  // prettier-ignore
const MODES = ["onsite", "hybrid", "remote"] as const;

export type OpportunityValues = {
  title: string;
  organizer: string;
  type: OpportunityType;
  mode: (typeof MODES)[number] | null;
  location: string;
  country: string;
  language: "en" | "fr" | "ar";
  deadline: string | null;
  funding: string | null;
  url: string;
  summary: string;
  eligibility: string[];
  benefits: string[];
  contact_email?: string;
  trust_level?: TrustLevel;
};

type Props = {
  /** submit = organisation (asks a contact email); admin = create/edit (asks a trust level). */
  variant: "submit" | "admin";
  initial?: Reviewed;
  submitLabel: string;
  busy: boolean;
  error?: string | null;
  disabled?: boolean;
  onSubmit: (values: OpportunityValues) => void;
  onCancel?: () => void;
};

const looksLikeUrl = (v: string) => /^(https?:\/\/)?[^\s/$.?#]+\.[^\s]+$/i.test(v.trim());
const looksLikeEmail = (v: string) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.trim());

export function OpportunityForm({ variant, initial, submitLabel, busy, error, disabled, onSubmit, onCancel }: Props) {
  const t = useTranslations("submit.form");
  const ta = useTranslations("admin");
  const to = useTranslations("opportunity");
  const { typeLabel } = useOptions();
  const [f, setF] = useState(() => ({
    title: initial?.title ?? "",
    organizer: initial?.organizer ?? "",
    type: (initial?.type ?? "hackathon") as OpportunityType,
    mode: initial?.mode ?? "",
    location: initial?.location ?? "",
    country: initial?.country ?? "Algeria",
    language: (initial?.language ?? "en") as OpportunityValues["language"],
    deadline: initial?.deadline ?? "",
    funding: initial?.funding ?? "",
    url: initial?.url ?? "",
    summary: initial?.summary ?? "",
    eligibility: (initial?.eligibility ?? []).join("\n"),
    benefits: initial?.benefits ?? [],
    contact_email: "",
    trust_level: (initial?.trust_level ?? "likely_safe") as TrustLevel,
  }));
  const [touched, setTouched] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((s) => ({ ...s, [k]: e.target.value }));

  const errors = {
    title: f.title.trim().length < 3 ? (f.title.trim() ? t("tooShort") : t("required")) : null,
    organizer: f.organizer.trim().length < 2 ? t("required") : null,
    url: !f.url.trim() ? t("required") : looksLikeUrl(f.url) ? null : t("badUrl"),
    contact: variant === "submit" && !looksLikeEmail(f.contact_email) ? t("badEmail") : null,
  };
  const show = (k: keyof typeof errors) => (touched ? errors[k] ?? undefined : undefined);

  function submit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (Object.values(errors).some(Boolean)) return;
    onSubmit({
      title: f.title.trim(),
      organizer: f.organizer.trim(),
      type: f.type,
      mode: (f.mode || null) as OpportunityValues["mode"],
      location: f.location.trim(),
      country: f.country.trim(),
      language: f.language,
      deadline: f.deadline || null,
      funding: f.funding.trim() || null,
      url: f.url.trim(),
      summary: f.summary.trim(),
      eligibility: f.eligibility.split("\n").map((l) => l.trim()).filter(Boolean).slice(0, 20),
      benefits: f.benefits,
      ...(variant === "submit" ? { contact_email: f.contact_email.trim() } : { trust_level: f.trust_level }),
    });
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("title")} error={show("title")}>
          {(p) => <Input {...p} value={f.title} maxLength={200} onChange={set("title")} placeholder={t("titlePlaceholder")} />}
        </Field>
        <Field label={t("organizer")} error={show("organizer")}>
          {(p) => <Input {...p} value={f.organizer} maxLength={200} onChange={set("organizer")} autoComplete="organization" />}
        </Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label={t("type")}>
          {(p) => (
            <Select {...p} value={f.type} onChange={set("type")}>
              {TYPES.map((type) => (
                <option key={type} value={type}>
                  {typeLabel(type)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label={t("mode")}>
          {(p) => (
            <Select {...p} value={f.mode} onChange={set("mode")}>
              <option value="">{t("modeAny")}</option>
              {MODES.map((m) => (
                <option key={m} value={m}>
                  {to(`mode.${m}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label={t("language")}>
          {(p) => (
            <Select {...p} value={f.language} onChange={set("language")}>
              {LOCALES.map((l) => (
                <option key={l} value={l}>
                  {LOCALE_NAMES[l]}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label={t("location")}>{(p) => <Input {...p} value={f.location} maxLength={120} onChange={set("location")} />}</Field>
        <Field label={t("country")}>{(p) => <Input {...p} value={f.country} maxLength={60} onChange={set("country")} autoComplete="country-name" />}</Field>
        <Field label={t("deadline")} hint={t("deadlineHint")}>
          {(p) => <Input {...p} type="date" value={f.deadline} onChange={set("deadline")} />}
        </Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t("url")} error={show("url")} hint={t("urlHint")}>
          {(p) => <Input {...p} type="url" inputMode="url" dir="ltr" value={f.url} maxLength={500} onChange={set("url")} placeholder="https://" />}
        </Field>
        <Field label={t("funding")}>
          {(p) => <Input {...p} value={f.funding} maxLength={120} onChange={set("funding")} placeholder={t("fundingPlaceholder")} />}
        </Field>
      </div>
      <TextArea label={t("summary")} value={f.summary} max={3000} rows={4} placeholder={t("summaryPlaceholder")} onChange={set("summary")} />
      <TextArea label={t("eligibility")} hint={t("eligibilityHint")} value={f.eligibility} max={6000} rows={3} onChange={set("eligibility")} />
      <div>
        <label htmlFor="benefits" className="text-[13px] font-bold text-ink">
          {t("benefits")}
        </label>
        <div className="pt-1.5">
          <TagInput id="benefits" values={f.benefits} onChange={(benefits) => setF((s) => ({ ...s, benefits }))} placeholder={t("benefitsPlaceholder")} max={20} />
        </div>
      </div>

      {variant === "submit" ? (
        <Field label={t("contact")} error={show("contact")} hint={t("contactHint")}>
          {(p) => <Input {...p} type="email" dir="ltr" autoComplete="email" value={f.contact_email} onChange={set("contact_email")} placeholder="contact@organisation.dz" />}
        </Field>
      ) : (
        <Field label={t("trust")}>
          {(p) => (
            <Select {...p} value={f.trust_level} onChange={set("trust_level")} className="sm:max-w-72">
              {TRUST_LEVELS.map((l) => (
                <option key={l} value={l}>
                  {ta(`trust.${l}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
      )}

      {error && <Alert>{error}</Alert>}
      <div className="flex flex-wrap gap-2.5 pt-1">
        <Button type="submit" size="md" disabled={busy || disabled}>
          {busy && <Spinner />}
          {submitLabel}
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" size="md" onClick={onCancel} disabled={busy}>
            {ta("cancel")}
          </Button>
        )}
      </div>
    </form>
  );
}

function TextArea({ label, hint, value, max, rows, placeholder, onChange }: { label: string; hint?: string; value: string; max: number; rows: number; placeholder?: string; onChange: (e: { target: { value: string } }) => void }) {
  const id = label.replace(/\W+/g, "-").toLowerCase();
  return (
    <div>
      <label htmlFor={id} className="text-[13px] font-bold text-ink">
        {label}
      </label>
      <textarea
        id={id}
        value={value}
        maxLength={max}
        rows={rows}
        placeholder={placeholder}
        onChange={onChange}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className={cn("mt-1.5 block w-full resize-y rounded-field border border-line bg-surface px-3.5 py-3 text-[15px] leading-[22px] text-ink outline-none placeholder:text-faint focus:border-brand focus:shadow-focus")}
      />
      {hint && (
        <p id={`${id}-hint`} className="pt-1.5 text-xs text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}
