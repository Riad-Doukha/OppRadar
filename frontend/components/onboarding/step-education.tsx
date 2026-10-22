"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useMemo, useState, type FormEvent } from "react";

import { Button, Spinner } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Pill, SectionLabel, Select } from "@/components/ui/inputs";
import { api, type Me, type Schemas } from "@/lib/api/client";
import { defined, intIn, orNull } from "@/lib/onboarding/body";
import { labelOf, useOptions } from "@/lib/onboarding/options";
import { useAutosave } from "@/lib/onboarding/save-status";

import { Row, StepFrame, useWizard } from "./frame";

type Level = NonNullable<Me["education_level"]>;

export function StepEducation() {
  const t = useTranslations("onboarding");
  const { CURRENT_YEARS, EDUCATION_LEVELS } = useOptions();
  const { me } = useWizard();
  const [f, setF] = useState(() => ({
    level: (me.education_level ?? "") as Level | "",
    field: me.field_of_study ?? "",
    institution: me.institution ?? "",
    currentYear: me.current_year?.toString() ?? "",
    graduationYear: me.graduation_year?.toString() ?? "",
    gpa: me.gpa_value?.toString() ?? "",
    gpaScale: (me.gpa_scale ?? 4).toString(),
  }));
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((s) => ({ ...s, [k]: e.target.value }));

  const gpa = f.gpa.trim() ? Number(f.gpa.replace(",", ".")) : null;
  const scale = Number(f.gpaScale);
  const gpaOk = gpa === null || (Number.isFinite(gpa) && gpa >= 0 && gpa <= scale);

  const body = useMemo(
    () =>
      defined({
        education_level: f.level || null,
        field_of_study: orNull(f.field),
        institution: orNull(f.institution),
        current_year: f.currentYear ? Number(f.currentYear) : null,
        graduation_year: intIn(f.graduationYear, 1950, 2100),
        // The API wants both GPA parts or neither.
        gpa_value: gpaOk ? gpa : undefined,
        gpa_scale: gpaOk ? (gpa === null ? null : (scale as 4 | 20)) : undefined,
      }),
    [f, gpa, gpaOk, scale],
  );
  const { flush } = useAutosave("/me/onboarding/education", body, { enabled: !me.is_demo });

  const errors = {
    level: f.level ? null : t("required"),
    field: f.field.trim() ? null : t("required"),
    year: f.currentYear || intIn(f.graduationYear, 1950, 2100) ? null : t("education.yearError"),
    gpa: gpaOk ? null : t("education.gpaError", { max: scale }),
  };

  return (
    <StepFrame step={2} errors={errors} flush={flush}>
      {(show) => {
        const err = (k: keyof typeof errors) => (show ? errors[k] ?? undefined : undefined);
        return (
          <>
            <div className="flex flex-col gap-4">
              <Row>
                <Field label={t("education.level")} error={err("level")}>
                  {(p) => (
                    <Select {...p} value={f.level} onChange={set("level")}>
                      <option value="">{t("choose")}</option>
                      {EDUCATION_LEVELS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </Select>
                  )}
                </Field>
                <Field label={t("education.field")} error={err("field")}>
                  {(p) => <Input {...p} value={f.field} onChange={set("field")} placeholder={t("education.fieldPlaceholder")} />}
                </Field>
              </Row>
              <Row>
                <Field label={t("education.institution")} hint={t("education.institutionHint")}>
                  {(p) => <Input {...p} autoComplete="organization" value={f.institution} onChange={set("institution")} placeholder="ENSIA" />}
                </Field>
                <Field label={t("education.year")} error={err("year")}>
                  {(p) => (
                    <div className="grid grid-cols-[1fr_110px] gap-2">
                      <Select {...p} value={f.currentYear} onChange={set("currentYear")} aria-label={t("education.currentYear")}>
                        <option value="">{t("education.graduated")}</option>
                        {CURRENT_YEARS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </Select>
                      <Input inputMode="numeric" maxLength={4} placeholder="2028" aria-label={t("education.graduationYear")} invalid={p.invalid} value={f.graduationYear} onChange={set("graduationYear")} />
                    </div>
                  )}
                </Field>
              </Row>
              <Row>
                <Field label={t("education.gpa")} error={err("gpa")} hint={t("education.gpaHint")}>
                  {(p) => (
                    <div className="grid grid-cols-[1fr_90px] gap-2">
                      <Input {...p} inputMode="decimal" placeholder="3.1" value={f.gpa} onChange={set("gpa")} />
                      <Select value={f.gpaScale} onChange={set("gpaScale")} aria-label={t("education.gpaScale")}>
                        <option value="4">/ 4</option>
                        <option value="20">/ 20</option>
                      </Select>
                    </div>
                  )}
                </Field>
              </Row>
            </div>

            <SectionLabel className="pt-7">{t("education.experience")}</SectionLabel>
            <Experiences />
            <SectionLabel className="pt-7">{t("education.certificates")}</SectionLabel>
            <Certificates />
          </>
        );
      }}
    </StepFrame>
  );
}

/* ----------------------------- experiences ------------------------------ */

type Experience = Schemas["Experience"];
type Certificate = Schemas["Certificate"];

function useRefreshMe() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["me"] });
}

function Experiences() {
  const t = useTranslations("onboarding.education");
  const { EXPERIENCE_KINDS } = useOptions();
  const { me } = useWizard();
  const [editing, setEditing] = useState<string | "new" | null>(null);
  return (
    <div className="flex flex-col gap-2.5 pt-2.5 pb-3">
      {me.experiences.map((x) =>
        editing === x.id ? (
          <ExperienceForm key={x.id} item={x} onDone={() => setEditing(null)} />
        ) : (
          <ItemCard key={x.id} onEdit={me.is_demo ? undefined : () => setEditing(x.id)}>
            <div className="flex flex-wrap items-center gap-2.5">
              <Pill className="h-6 px-2.5 text-[11px]">{labelOf(EXPERIENCE_KINDS, x.kind)}</Pill>
              <span className="text-[15px] font-bold text-ink">{x.title}</span>
              {x.year && <span className="font-mono text-xs text-muted">{x.year}</span>}
            </div>
            {(x.organization || x.description) && (
              <p className="pt-1 text-sm text-body">{[x.organization, x.description].filter(Boolean).join(": ")}</p>
            )}
          </ItemCard>
        ),
      )}
      {editing === "new" ? (
        <ExperienceForm onDone={() => setEditing(null)} />
      ) : (
        !me.is_demo && (
          <Button variant="outline" size="sm" className="self-start text-sm" onClick={() => setEditing("new")}>
            {t("addExperience", { more: String(me.experiences.length > 0) })}
          </Button>
        )
      )}
    </div>
  );
}

function ExperienceForm({ item, onDone }: { item?: Experience; onDone: () => void }) {
  const t = useTranslations("onboarding.education");
  const { EXPERIENCE_KINDS } = useOptions();
  const refresh = useRefreshMe();
  const [f, setF] = useState({
    kind: item?.kind ?? "internship",
    title: item?.title ?? "",
    organization: item?.organization ?? "",
    year: item?.year?.toString() ?? "",
    description: item?.description ?? "",
  });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((s) => ({ ...s, [k]: e.target.value }));
  const year = intIn(f.year, 1950, 2100);
  const valid = f.title.trim() && year !== undefined;
  const { busy, error, run } = useAction(async () => {
    await refresh();
    onDone();
  });

  const save = (e: FormEvent) => {
    e.preventDefault();
    return run(async () => {
      const body = JSON.stringify({ ...f, title: f.title.trim(), year });
      await api(item ? `/me/experiences/${item.id}` : "/me/experiences", { method: item ? "PATCH" : "POST", body });
    });
  };
  const remove = () => run(() => api(`/me/experiences/${item!.id}`, { method: "DELETE" }));

  return (
    <form onSubmit={save} className="flex flex-col gap-3 rounded-field border border-brand bg-page p-4">
      <div className="grid gap-3 sm:grid-cols-[160px_1fr]">
        <Field label={t("type")}>
          {(p) => (
            <Select {...p} value={f.kind} onChange={set("kind")}>
              {EXPERIENCE_KINDS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </Select>
          )}
        </Field>
        <Field label={t("title")}>{(p) => <Input {...p} value={f.title} onChange={set("title")} placeholder={t("titlePlaceholder")} />}</Field>
      </div>
      <div className="grid gap-3 sm:grid-cols-[1fr_110px]">
        <Field label={t("organization")}>{(p) => <Input {...p} value={f.organization} onChange={set("organization")} placeholder="Yassir" />}</Field>
        <Field label={t("yearLabel")} error={year === undefined ? "1950–2100" : undefined}>
          {(p) => <Input {...p} inputMode="numeric" maxLength={4} value={f.year} onChange={set("year")} placeholder="2024" />}
        </Field>
      </div>
      <Field label={t("whatDid")}>
        {(p) => <Input {...p} maxLength={1000} value={f.description} onChange={set("description")} placeholder={t("whatDidPlaceholder")} />}
      </Field>
      <FormButtons busy={busy} valid={Boolean(valid)} error={error} onCancel={onDone} onDelete={item ? remove : undefined} />
    </form>
  );
}

/* ----------------------------- certificates ----------------------------- */

function Certificates() {
  const t = useTranslations("onboarding.education");
  const { me } = useWizard();
  const [editing, setEditing] = useState<string | "new" | null>(null);
  return (
    <div className="flex flex-col gap-2.5 pt-2.5">
      {me.certificates.map((c) =>
        editing === c.id ? (
          <CertificateForm key={c.id} item={c} onDone={() => setEditing(null)} />
        ) : (
          <ItemCard key={c.id} onEdit={me.is_demo ? undefined : () => setEditing(c.id)}>
            <p className="text-[15px] font-bold text-ink">{c.issuer ? t("at", { title: c.title, issuer: c.issuer }) : c.title}</p>
            <p className="text-sm text-body">
              {[c.year, c.credential_url && t("credentialLink")].filter(Boolean).join(" · ")}
            </p>
          </ItemCard>
        ),
      )}
      {editing === "new" ? (
        <CertificateForm onDone={() => setEditing(null)} />
      ) : (
        !me.is_demo && (
          <Button variant="outline" size="sm" className="self-start text-sm" onClick={() => setEditing("new")}>
            {t("addCertificate", { more: String(me.certificates.length > 0) })}
          </Button>
        )
      )}
    </div>
  );
}

function CertificateForm({ item, onDone }: { item?: Certificate; onDone: () => void }) {
  const t = useTranslations("onboarding.education");
  const refresh = useRefreshMe();
  const [f, setF] = useState({ title: item?.title ?? "", issuer: item?.issuer ?? "", year: item?.year?.toString() ?? "", url: item?.credential_url ?? "" });
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((s) => ({ ...s, [k]: e.target.value }));
  const year = intIn(f.year, 1950, 2100);
  const valid = f.title.trim() && year !== undefined;
  const { busy, error, run } = useAction(async () => {
    await refresh();
    onDone();
  });

  const save = (e: FormEvent) => {
    e.preventDefault();
    return run(async () => {
      const body = JSON.stringify({ title: f.title.trim(), issuer: f.issuer.trim(), year, credential_url: orNull(f.url) });
      await api(item ? `/me/certificates/${item.id}` : "/me/certificates", { method: item ? "PATCH" : "POST", body });
    });
  };
  const remove = () => run(() => api(`/me/certificates/${item!.id}`, { method: "DELETE" }));

  return (
    <form onSubmit={save} className="flex flex-col gap-3 rounded-field border border-brand bg-page p-4">
      <Row>
        <Field label={t("certificate")}>{(p) => <Input {...p} value={f.title} onChange={set("title")} placeholder={t("certificatePlaceholder")} />}</Field>
        <Field label={t("issuer")}>{(p) => <Input {...p} value={f.issuer} onChange={set("issuer")} placeholder="IBM" />}</Field>
      </Row>
      <div className="grid gap-3 sm:grid-cols-[110px_1fr]">
        <Field label={t("yearLabel")} error={year === undefined ? "1950–2100" : undefined}>
          {(p) => <Input {...p} inputMode="numeric" maxLength={4} value={f.year} onChange={set("year")} placeholder="2023" />}
        </Field>
        <Field label={t("credential")}>{(p) => <Input {...p} type="url" value={f.url} onChange={set("url")} placeholder="https://" />}</Field>
      </div>
      <FormButtons busy={busy} valid={Boolean(valid)} error={error} onCancel={onDone} onDelete={item ? remove : undefined} />
    </form>
  );
}

/* -------------------------------- shared -------------------------------- */

function ItemCard({ children, onEdit }: { children: React.ReactNode; onEdit?: () => void }) {
  const t = useTranslations("common");
  return (
    <div className="flex items-start justify-between gap-3 rounded-field border border-line bg-surface px-4 py-3.5">
      <div className="min-w-0">{children}</div>
      {onEdit && (
        <Button variant="ghost" className="h-8 px-3 text-[13px]" onClick={onEdit}>
          {t("edit")}
        </Button>
      )}
    </div>
  );
}

function useAction(after: () => Promise<void>) {
  const t = useTranslations("common.errors");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await after();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("generic"));
    }
    setBusy(false);
  }
  return { busy, error, run };
}

function FormButtons({ busy, valid, error, onCancel, onDelete }: { busy: boolean; valid: boolean; error: string | null; onCancel: () => void; onDelete?: () => void }) {
  const t = useTranslations("common");
  const te = useTranslations("onboarding.education");
  return (
    <div>
      {error && <p className="pb-2 text-xs text-danger">{error}</p>}
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" size="sm" disabled={busy || !valid}>
          {busy && <Spinner />} {t("save")}
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={onCancel} disabled={busy}>
          {t("cancel")}
        </Button>
        {onDelete && (
          <Button type="button" variant="ghost" size="sm" className="ms-auto text-danger hover:text-danger" onClick={onDelete} disabled={busy}>
            {te("delete")}
          </Button>
        )}
      </div>
    </div>
  );
}
