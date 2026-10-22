"use client";

import { useMemo, useState } from "react";

import { Field } from "@/components/ui/field";
import { ChoiceCard, Pill, Segmented, Select, TagInput } from "@/components/ui/inputs";
import type { Schemas } from "@/lib/api/client";
import { defined } from "@/lib/onboarding/body";
import { AVAILABILITY, INTEREST_SUGGESTIONS, OPPORTUNITY_TYPES, PREFERRED_LOCATIONS, SKILL_LEVELS, SKILL_SUGGESTIONS } from "@/lib/onboarding/options";
import { useAutosave } from "@/lib/onboarding/save-status";

import { Row, StepFrame, useWizard } from "./frame";

const MIN_SKILLS = 3;
type SkillLevel = (typeof SKILL_LEVELS)[number]["value"];
type OppType = Schemas["OpportunityOut"]["type"];

export function StepSkills() {
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
    skills: skills.length >= MIN_SKILLS ? null : `Add at least ${MIN_SKILLS} skills.`,
    interests: interests.length ? null : "Add at least one interest.",
    types: types.length ? null : "Pick at least one type.",
    location: location ? null : "Required.",
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
                Skills * <span className="font-normal text-muted">add at least {MIN_SKILLS}</span>
              </label>
              <div className="pt-1.5">
                <TagInput id="skills" values={skills.map((s) => s.name)} onChange={setSkillNames} placeholder="Type a skill" suggestions={SKILL_SUGGESTIONS} invalid={Boolean(err("skills"))} />
              </div>
              {err("skills") && <p className="pt-1.5 text-xs text-danger">{err("skills")}</p>}
            </div>

            {skills.length > 0 && (
              <div>
                <p className="text-[13px] font-bold text-ink">Level per skill</p>
                <ul className="flex flex-col gap-2 pt-1.5">
                  {skills.map((s, i) => (
                    <li key={s.name} className="flex flex-wrap items-center gap-x-3.5 gap-y-1.5">
                      <Pill className="h-8 w-[120px] justify-center truncate">{s.name}</Pill>
                      <Segmented
                        label={`${s.name} level`}
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
                Interests * <span className="font-normal text-muted">(tags)</span>
              </label>
              <div className="pt-1.5">
                <TagInput id="interests" values={interests} onChange={setInterests} placeholder="Add an interest…" suggestions={INTEREST_SUGGESTIONS} max={30} invalid={Boolean(err("interests"))} />
              </div>
              {err("interests") && <p className="pt-1.5 text-xs text-danger">{err("interests")}</p>}
            </div>

            <fieldset>
              <legend className="text-[13px] font-bold text-ink">Opportunity types wanted *</legend>
              <div className="grid grid-cols-2 gap-2.5 pt-1.5 sm:grid-cols-3">
                {OPPORTUNITY_TYPES.map((t) => {
                  const on = types.includes(t.value);
                  return (
                    <ChoiceCard key={t.value} checked={on} onChange={(v) => setTypes((cur) => (v ? [...cur, t.value] : cur.filter((x) => x !== t.value)))}>
                      <span className={on ? "text-sm font-bold text-ink" : "text-sm font-medium text-muted"}>{t.label}</span>
                    </ChoiceCard>
                  );
                })}
              </div>
              {err("types") && <p className="pt-1.5 text-xs text-danger">{err("types")}</p>}
            </fieldset>

            <Row>
              <Field label="Preferred location *" error={err("location") ?? undefined}>
                {(p) => (
                  <Select {...p} value={location} onChange={(e) => setLocation(e.target.value)}>
                    <option value="">Choose…</option>
                    {PREFERRED_LOCATIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </Select>
                )}
              </Field>
              <Field label="Availability (optional)">
                {(p) => (
                  <Select {...p} value={availability} onChange={(e) => setAvailability(e.target.value)}>
                    <option value="">Not specified</option>
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
