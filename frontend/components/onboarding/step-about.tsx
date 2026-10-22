"use client";

import { useMemo, useState } from "react";

import { Field, Input } from "@/components/ui/field";
import { Pill, Segmented, Select } from "@/components/ui/inputs";
import { defined, intIn, orNull } from "@/lib/onboarding/body";
import { COUNTRIES, LANGUAGE_LEVELS, LANGUAGE_SUGGESTIONS, NATIONALITIES, WILAYAS } from "@/lib/onboarding/options";
import { useAutosave } from "@/lib/onboarding/save-status";

import { CvUpload, type Prefill } from "./cv-upload";
import { Row, StepFrame, useWizard } from "./frame";

type Level = (typeof LANGUAGE_LEVELS)[number]["value"];

export function StepAbout({ onApplyPrefill }: { onApplyPrefill: (p: Prefill) => Promise<void> }) {
  const { me } = useWizard();
  const [f, setF] = useState(() => ({
    fullName: me.full_name ?? "",
    birthYear: me.birth_year?.toString() ?? "",
    nationality: me.nationality ?? "",
    country: me.country ?? "",
    wilaya: me.wilaya ?? "",
    languages: me.languages.map((l) => ({ language: l.language, level: (l.level ?? "good") as Level })),
  }));
  const [newLang, setNewLang] = useState("");
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((s) => ({ ...s, [k]: e.target.value }));

  const body = useMemo(
    () =>
      defined({
        full_name: f.fullName.trim() || undefined,
        birth_year: intIn(f.birthYear, 1940, 2020),
        nationality: orNull(f.nationality),
        country: orNull(f.country),
        wilaya: orNull(f.wilaya),
        languages: f.languages,
      }),
    [f],
  );
  const { flush } = useAutosave("/me/onboarding/about", body, { enabled: !me.is_demo });

  const errors = {
    fullName: f.fullName.trim().length < 2 ? "Enter your full name." : null,
    birthYear: intIn(f.birthYear, 1940, 2020) ? null : "Enter a year between 1940 and 2020.",
    nationality: f.nationality.trim() ? null : "Required.",
    country: f.country.trim() ? null : "Required.",
    wilaya: f.wilaya.trim() ? null : "Required.",
  };
  const inAlgeria = f.country.trim().toLowerCase() === "algeria";

  function addLanguage(name: string) {
    const v = name.trim();
    if (v && !f.languages.some((l) => l.language.toLowerCase() === v.toLowerCase()) && f.languages.length < 10)
      setF((s) => ({ ...s, languages: [...s.languages, { language: v, level: "good" }] }));
    setNewLang("");
  }

  return (
    <StepFrame step={1} errors={errors} flush={flush}>
      {(show) => {
        const err = (k: keyof typeof errors) => (show ? errors[k] ?? undefined : undefined);
        return (
          <>
            <CvUpload readOnly={me.is_demo} onApply={onApplyPrefill} />

            <div className="flex flex-col gap-4 pt-[26px]">
              <div className="grid gap-4 sm:grid-cols-[1fr_200px]">
                <Field label="Full name *" error={err("fullName")}>
                  {(p) => <Input {...p} autoComplete="name" value={f.fullName} onChange={set("fullName")} />}
                </Field>
                <Field label="Birth year *" error={err("birthYear")} hint="Many opportunities have age limits">
                  {(p) => <Input {...p} inputMode="numeric" maxLength={4} placeholder="2003" value={f.birthYear} onChange={set("birthYear")} />}
                </Field>
              </div>
              <Row>
                <Field label="Nationality *" error={err("nationality")}>
                  {(p) => <Input {...p} list="nationalities" value={f.nationality} onChange={set("nationality")} placeholder="Algerian" />}
                </Field>
                <Field label="Country *" error={err("country")}>
                  {(p) => <Input {...p} list="countries" autoComplete="country-name" value={f.country} onChange={set("country")} placeholder="Algeria" />}
                </Field>
              </Row>
              <Row>
                <Field label={inAlgeria ? "Wilaya *" : "City / region *"} error={err("wilaya")}>
                  {(p) =>
                    inAlgeria ? (
                      <Select {...p} value={f.wilaya} onChange={set("wilaya")}>
                        <option value="">Choose your wilaya</option>
                        {WILAYAS.map((w, i) => (
                          <option key={w} value={w}>
                            {String(i + 1).padStart(2, "0")} · {w}
                          </option>
                        ))}
                      </Select>
                    ) : (
                      <Input {...p} value={f.wilaya} onChange={set("wilaya")} />
                    )
                  }
                </Field>
              </Row>
              <datalist id="nationalities">{NATIONALITIES.map((n) => <option key={n} value={n} />)}</datalist>
              <datalist id="countries">{COUNTRIES.map((c) => <option key={c} value={c} />)}</datalist>

              <div>
                <p className="text-[13px] font-bold text-ink">
                  Languages: <span className="font-normal text-muted">with your level</span>
                </p>
                <p className="pt-1.5 text-xs text-muted">Used when an opportunity requires a language level.</p>
                <ul className="flex flex-col gap-2.5 pt-2.5">
                  {f.languages.map((l, i) => (
                    <li key={l.language} className="flex flex-wrap items-center gap-x-3.5 gap-y-2">
                      <Pill className="h-8 w-[130px] justify-center" onRemove={() => setF((s) => ({ ...s, languages: s.languages.filter((_, j) => j !== i) }))}>
                        {l.language}
                      </Pill>
                      <Segmented
                        label={`${l.language} level`}
                        value={l.level}
                        options={LANGUAGE_LEVELS}
                        onChange={(level) => setF((s) => ({ ...s, languages: s.languages.map((x, j) => (j === i ? { ...x, level } : x)) }))}
                      />
                    </li>
                  ))}
                  <li className="flex items-center gap-2">
                    <input
                      value={newLang}
                      list="languages"
                      onChange={(e) => setNewLang(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          addLanguage(newLang);
                        }
                      }}
                      onBlur={() => newLang && addLanguage(newLang)}
                      placeholder="+ Add language"
                      aria-label="Add a language"
                      className="h-8 w-[130px] rounded-full border border-line bg-surface px-3.5 text-center text-[13px] font-medium text-ink outline-none placeholder:text-faint focus:border-brand focus:text-left"
                    />
                    <datalist id="languages">{LANGUAGE_SUGGESTIONS.map((l) => <option key={l} value={l} />)}</datalist>
                  </li>
                </ul>
              </div>
            </div>
          </>
        );
      }}
    </StepFrame>
  );
}
