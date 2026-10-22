"use client";

import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import { Field } from "@/components/ui/field";
import { ChoiceCard, Pill, Segmented, Select, TagInput } from "@/components/ui/inputs";
import type { Schemas } from "@/lib/api/client";
import { defined } from "@/lib/onboarding/body";
import { useOptions } from "@/lib/onboarding/options";
import { useAutosave } from "@/lib/onboarding/save-status";

import { Row, StepFrame, useWizard } from "./frame";

const MIN_SKILLS = 3;
type SkillLevel = "beginner" | "intermediate" | "advanced";
type OppType = Schemas["OpportunityOut"]["type"];

export function StepSkills() {
  const t = useTranslations("onboarding");
  const { AVAILABILITY, INTEREST_SUGGESTIONS, OPPORTUNITY_TYPES, PREFERRED_LOCATIONS, SKILL_LEVELS, SKILL_SUGGESTIONS } = useOptions();
  const { me } = useWizard();
  const [skills, setSkills] = useState(() => me.skills.map((s) => ({ name: s.name, level: (s.level ?? null) as SkillLevel | null })));
  const [interests, setInterests] = useState<string[]>(() => me.interests);
  const [types, setTypes] = useState<OppType[]>(() => me.opportunity_types);
  const [location, setLocation] = useState(me.preferred_location ?? "");
  const [availability, setAvailability] = useState(me.availability ?? "");

  const body = useMemo(
    () =>
      defined({
        skills,
        interests,
        opportunity_types: types,
        preferred_location: location || null,
        availability: availability || null,
      }),
    [skills, interests, types, location, availability],
  );
  const { flush } = useAutosave("/me/onboarding/skills", body, { enabled: !me.is_demo });

  const errors = {
    skills: skills.length >= MIN_SKILLS ? null : t("skills.needSkills", { n: MIN_SKILLS }),
    interests: interests.length ? null : t("skills.needInterest"),
    types: types.length ? null : t("skills.needType"),
    location: location ? null : t("required"),
  };

  const setSkillNames = (names: string[]) =>
    setSkills((cur) => names.map((name) => cur.find((s) => s.name === name) ?? { name, level: null }));

  return (
    <StepFrame step={3} errors={errors} flush={flush}>
      {(show) => {
        const err = (k: keyof typeof errors) => (show ? errors[k] : null);
        return (
          <div className="flex flex-col gap-5">
            <div>
              <label htmlFor="skills" className="text-[13px] font-bold text-ink">
                {t("skills.label")} <span className="font-normal text-muted">{t("skills.min", { n: MIN_SKILLS })}</span>
              </label>
              <div className="pt-1.5">
                <TagInput id="skills" values={skills.map((s) => s.name)} onChange={setSkillNames} placeholder={t("skills.placeholder")} suggestions={SKILL_SUGGESTIONS} invalid={Boolean(err("skills"))} />
              </div>
              {err("skills") && <p className="pt-1.5 text-xs text-danger">{err("skills")}</p>}
            </div>

            {skills.length > 0 && (
              <div>
                <p className="text-[13px] font-bold text-ink">{t("skills.levelPer")}</p>
                <ul className="flex flex-col gap-2 pt-1.5">
                  {skills.map((s, i) => (
                    <li key={s.name} className="flex flex-wrap items-center gap-x-3.5 gap-y-1.5">
                      <Pill className="h-8 w-[120px] justify-center truncate">{s.name}</Pill>
                      <Segmented
                        label={t("about.levelOf", { name: s.name })}
                        value={s.level}
                        options={SKILL_LEVELS}
                        onChange={(level) => setSkills((cur) => cur.map((x, j) => (j === i ? { ...x, level } : x)))}
                      />
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div>
              <label htmlFor="interests" className="text-[13px] font-bold text-ink">
                {t("skills.interests")} <span className="font-normal text-muted">{t("skills.tags")}</span>
              </label>
              <div className="pt-1.5">
                <TagInput id="interests" values={interests} onChange={setInterests} placeholder={t("skills.interestPlaceholder")} suggestions={INTEREST_SUGGESTIONS} max={30} invalid={Boolean(err("interests"))} />
              </div>
              {err("interests") && <p className="pt-1.5 text-xs text-danger">{err("interests")}</p>}
            </div>

            <fieldset>
              <legend className="text-[13px] font-bold text-ink">{t("skills.types")}</legend>
              <div className="grid grid-cols-2 gap-2.5 pt-1.5 sm:grid-cols-3">
                {OPPORTUNITY_TYPES.map((o) => {
                  const on = types.includes(o.value);
                  return (
                    <ChoiceCard key={o.value} checked={on} onChange={(v) => setTypes((cur) => (v ? [...cur, o.value] : cur.filter((x) => x !== o.value)))}>
                      <span className={on ? "text-sm font-bold text-ink" : "text-sm font-medium text-muted"}>{o.label}</span>
                    </ChoiceCard>
                  );
                })}
              </div>
              {err("types") && <p className="pt-1.5 text-xs text-danger">{err("types")}</p>}
            </fieldset>

            <Row>
              <Field label={t("skills.location")} error={err("location") ?? undefined}>
                {(p) => (
                  <Select {...p} value={location} onChange={(e) => setLocation(e.target.value)}>
                    <option value="">{t("choose")}</option>
                    {PREFERRED_LOCATIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </Select>
                )}
              </Field>
              <Field label={t("skills.availability")}>
                {(p) => (
                  <Select {...p} value={availability} onChange={(e) => setAvailability(e.target.value)}>
                    <option value="">{t("skills.notSpecified")}</option>
                    {AVAILABILITY.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </Select>
                )}
              </Field>
            </Row>
          </div>
        );
      }}
    </StepFrame>
  );
}
