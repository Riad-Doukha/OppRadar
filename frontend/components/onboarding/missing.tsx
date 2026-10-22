"use client";

import { useTranslations } from "next-intl";

import { STEPS } from "@/lib/onboarding/options";

import { useWizard } from "./frame";

// Keys from the API's onboarding.missing list (backend/app/services/profiles.py),
// labelled by onboarding.missing.fields.<key with dots as underscores>.
const KNOWN = [
  "about.full_name",
  "about.birth_year",
  "about.nationality",
  "about.country",
  "about.wilaya",
  "education.education_level",
  "education.field_of_study",
  "education.current_or_graduation_year",
  "skills.skills",
  "skills.interests",
  "skills.opportunity_types",
  "skills.preferred_location",
  "goals.goal",
  "alerts.channel",
  "alerts.consent.terms_privacy",
  "alerts.consent.agent_matching",
  "alerts.consent.ai_cv_processing",
];

/** "Some required fields are still empty" with a link to each step. */
export function MissingList({ missing }: { missing: string[] }) {
  const t = useTranslations("onboarding.missing");
  const { goTo } = useWizard();
  const known = missing.filter((m) => KNOWN.includes(m));
  if (!known.length) return <p>{t("couldNotFinish")}</p>;
  return (
    <>
      <p>{t("intro")}</p>
      <ul className="list-disc pt-1 ps-4">
        {known.map((key) => {
          const step = STEPS.find((s) => s.slug === key.split(".")[0]);
          return (
            <li key={key}>
              {t(`fields.${key.replaceAll(".", "_")}` as Parameters<typeof t>[0])}
              {step && (
                <>
                  {" — "}
                  <button type="button" className="font-bold underline" onClick={() => goTo(step.n)}>
                    {t("step", { n: step.n })}
                  </button>
                </>
              )}
            </li>
          );
        })}
      </ul>
    </>
  );
}
