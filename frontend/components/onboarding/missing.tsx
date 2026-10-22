"use client";

import { STEPS } from "@/lib/onboarding/options";

import { useWizard } from "./frame";

// Keys from the API's onboarding.missing list (backend/app/services/profiles.py).
const LABELS: Record<string, string> = {
  "about.full_name": "Full name",
  "about.birth_year": "Birth year",
  "about.nationality": "Nationality",
  "about.country": "Country",
  "about.wilaya": "Wilaya",
  "education.education_level": "Education level",
  "education.field_of_study": "Field of study",
  "education.current_or_graduation_year": "Current or graduation year",
  "skills.skills": "At least 3 skills",
  "skills.interests": "Interests",
  "skills.opportunity_types": "Opportunity types",
  "skills.preferred_location": "Preferred location",
  "goals.goal": "Goal",
  "alerts.channel": "A notification channel",
  "alerts.consent.terms_privacy": "Terms and Privacy consent",
  "alerts.consent.agent_matching": "Matching consent",
  "alerts.consent.ai_cv_processing": "CV processing consent",
};

/** "Some required fields are still empty" with a link to each step. */
export function MissingList({ missing }: { missing: string[] }) {
  const { goTo } = useWizard();
  const known = missing.filter((m) => m in LABELS);
  if (!known.length) return <p>We couldn&apos;t finish your setup. Please try again.</p>;
  return (
    <>
      <p>Some required fields are still empty:</p>
      <ul className="list-disc pt-1 pl-4">
        {known.map((key) => {
          const step = STEPS.find((s) => s.slug === key.split(".")[0]);
          return (
            <li key={key}>
              {LABELS[key]}
              {step && (
                <>
                  {" — "}
                  <button type="button" className="font-bold underline" onClick={() => goTo(step.n)}>
                    step {step.n}
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
