// Choices shown in the onboarding wizard and profile. Values match the API
// enums (backend/app/models.py) and are what gets stored; labels come from the
// `options` messages, so useOptions() returns them in the visitor's language.

import { useTranslations } from "next-intl";
import { useMemo } from "react";

import type { Me, Schemas } from "@/lib/api/client";

type Option<T extends string | number> = { value: T; label: string };

const EDUCATION = ["bac", "licence", "master", "engineer", "phd", "other"] as const satisfies readonly NonNullable<Me["education_level"]>[];
const YEARS = [1, 2, 3, 4, 5, 6, 7];
const LANGUAGE_LEVEL = ["basic", "good", "fluent"] as const;
const SKILL_LEVEL = ["beginner", "intermediate", "advanced"] as const;
const WIZARD_TYPES = ["hackathon", "datathon", "competition", "scholarship", "internship", "volunteer"] as const satisfies readonly OpportunityType[];
const LOCATION = ["algeria", "abroad", "remote", "anywhere"] as const satisfies readonly NonNullable<Me["preferred_location"]>[];
const AVAIL = ["full_time", "part_time_10_20", "under_10h", "flexible"] as const satisfies readonly NonNullable<Me["availability"]>[];
const FREQUENCY = ["instant", "daily", "weekly"] as const satisfies readonly Me["notifications"]["frequency"][];
const EXPERIENCE = ["internship", "hackathon", "competition", "job", "volunteer", "other"] as const satisfies readonly Schemas["Experience"]["kind"][];

export type OpportunityType = Schemas["OpportunityOut"]["type"];

// Stored as typed (English) values; the label is translated where a list exists.
const COUNTRY = [
  "Algeria", "Morocco", "Tunisia", "Egypt", "Libya", "Mauritania", "France", "Germany", "Spain",
  "Italy", "United Kingdom", "Canada", "United States", "Turkey", "Saudi Arabia", "Qatar",
  "United Arab Emirates", "Malaysia", "China", "Other",
] as const;
const NATIONALITY = ["Algerian", "Moroccan", "Tunisian", "Egyptian", "Libyan", "Mauritanian", "French", "Other"] as const;

// The 58 wilayas, in official order (stored by their Latin name).
export const WILAYAS = [
  "Adrar", "Chlef", "Laghouat", "Oum El Bouaghi", "Batna", "Béjaïa", "Biskra", "Béchar", "Blida",
  "Bouira", "Tamanrasset", "Tébessa", "Tlemcen", "Tiaret", "Tizi Ouzou", "Algiers", "Djelfa",
  "Jijel", "Sétif", "Saïda", "Skikda", "Sidi Bel Abbès", "Annaba", "Guelma", "Constantine",
  "Médéa", "Mostaganem", "M'Sila", "Mascara", "Ouargla", "Oran", "El Bayadh", "Illizi",
  "Bordj Bou Arréridj", "Boumerdès", "El Tarf", "Tindouf", "Tissemsilt", "El Oued", "Khenchela",
  "Souk Ahras", "Tipaza", "Mila", "Aïn Defla", "Naâma", "Aïn Témouchent", "Ghardaïa", "Relizane",
  "Timimoun", "Bordj Badji Mokhtar", "Ouled Djellal", "Béni Abbès", "In Salah", "In Guezzam",
  "Touggourt", "Djanet", "El M'Ghair", "El Meniaa",
] as const;

export const STEPS = [
  { n: 1, slug: "about" },
  { n: 2, slug: "education" },
  { n: 3, slug: "skills" },
  { n: 4, slug: "goals" },
  { n: 5, slug: "alerts" },
] as const;

export function labelOf<T extends string | number>(options: readonly Option<T>[], value: T | null | undefined) {
  return options.find((o) => o.value === value)?.label ?? "";
}

/** Every option list with labels in the current language. */
export function useOptions() {
  const t = useTranslations("options");
  return useMemo(() => {
    const list = <T extends string>(values: readonly T[], group: string) =>
      values.map((value) => ({ value, label: t(`${group}.${value}` as Parameters<typeof t>[0]) }));
    const known = <T extends string>(group: string, values: readonly T[]) => (v: string | null | undefined) =>
      v && (values as readonly string[]).includes(v) ? t(`${group}.${v}` as Parameters<typeof t>[0]) : (v ?? "");
    return {
      EDUCATION_LEVELS: list(EDUCATION, "education"),
      CURRENT_YEARS: YEARS.map((n) => ({ value: n, label: t("year", { n }) })),
      LANGUAGE_LEVELS: list(LANGUAGE_LEVEL, "languageLevel"),
      SKILL_LEVELS: list(SKILL_LEVEL, "skillLevel"),
      OPPORTUNITY_TYPES: list(WIZARD_TYPES, "type"),
      PREFERRED_LOCATIONS: list(LOCATION, "location"),
      AVAILABILITY: list(AVAIL, "availability"),
      FREQUENCIES: list(FREQUENCY, "frequency"),
      EXPERIENCE_KINDS: list(EXPERIENCE, "experience"),
      COUNTRIES: list(COUNTRY, "country"),
      NATIONALITIES: list(NATIONALITY, "nationality"),
      WILAYAS: list(WILAYAS, "wilaya"),
      SKILL_SUGGESTIONS: t("suggest.skills").split("|"),
      INTEREST_SUGGESTIONS: t("suggest.interests").split("|"),
      LANGUAGE_SUGGESTIONS: t("suggest.languages").split("|"),
      /** Any opportunity type (the feed has more than the wizard offers). */
      typeLabel: (type: OpportunityType) => t(`type.${type}`),
      stepTitle: (slug: (typeof STEPS)[number]["slug"]) => t(`steps.${slug}`),
      /** Stored English country / nationality / wilaya → its label (free text passes through). */
      countryLabel: known("country", COUNTRY),
      nationalityLabel: known("nationality", NATIONALITY),
      wilayaLabel: known("wilaya", WILAYAS),
    };
  }, [t]);
}

export type Options = ReturnType<typeof useOptions>;
