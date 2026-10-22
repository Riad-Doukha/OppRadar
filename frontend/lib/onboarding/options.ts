// Choices shown in the onboarding wizard. Values match the API enums
// (backend/app/models.py); labels are the copy from the Figma design.

import type { Me, Schemas } from "@/lib/api/client";

type Option<T extends string | number> = { value: T; label: string };

export const EDUCATION_LEVELS: Option<NonNullable<Me["education_level"]>>[] = [
  { value: "bac", label: "Baccalaureate" },
  { value: "licence", label: "Bachelor (Licence)" },
  { value: "master", label: "Master" },
  { value: "engineer", label: "Engineering degree" },
  { value: "phd", label: "PhD" },
  { value: "other", label: "Other" },
];

export const CURRENT_YEARS: Option<number>[] = [1, 2, 3, 4, 5, 6, 7].map((n) => ({
  value: n,
  label: `${n}${["st", "nd", "rd"][n - 1] ?? "th"} year`,
}));

export const LANGUAGE_LEVELS = [
  { value: "basic", label: "Basic" },
  { value: "good", label: "Good" },
  { value: "fluent", label: "Fluent" },
] as const;

export const SKILL_LEVELS = [
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
] as const;

export const OPPORTUNITY_TYPES: Option<Schemas["OpportunityOut"]["type"]>[] = [
  { value: "hackathon", label: "Hackathon" },
  { value: "datathon", label: "Datathon" },
  { value: "competition", label: "Competition" },
  { value: "scholarship", label: "Scholarship" },
  { value: "internship", label: "Internship" },
  { value: "volunteer", label: "Volunteering" },
];

export const PREFERRED_LOCATIONS: Option<NonNullable<Me["preferred_location"]>>[] = [
  { value: "algeria", label: "In Algeria" },
  { value: "abroad", label: "Abroad" },
  { value: "remote", label: "Remote only" },
  { value: "anywhere", label: "Anywhere" },
];

export const AVAILABILITY: Option<NonNullable<Me["availability"]>>[] = [
  { value: "full_time", label: "Full-time" },
  { value: "part_time_10_20", label: "Part-time (10 - 20 h/week)" },
  { value: "under_10h", label: "Under 10 h/week" },
  { value: "flexible", label: "Flexible" },
];

export const FREQUENCIES: Option<Me["notifications"]["frequency"]>[] = [
  { value: "instant", label: "Instant: as soon as a match is found" },
  { value: "daily", label: "Daily digest" },
  { value: "weekly", label: "Weekly digest" },
];

export const EXPERIENCE_KINDS: Option<Schemas["Experience"]["kind"]>[] = [
  { value: "internship", label: "Internship" },
  { value: "hackathon", label: "Hackathon" },
  { value: "competition", label: "Competition" },
  { value: "job", label: "Job" },
  { value: "volunteer", label: "Volunteering" },
  { value: "other", label: "Other" },
];

export const SKILL_SUGGESTIONS = ["Machine learning", "Statistics", "SQL", "Data visualization", "Git"];
export const INTEREST_SUGGESTIONS = ["AI", "Data", "Web development", "Entrepreneurship", "Volunteering"];
export const LANGUAGE_SUGGESTIONS = ["Arabic", "French", "English", "Tamazight", "Spanish", "German"];

export const COUNTRIES = [
  "Algeria", "Morocco", "Tunisia", "Egypt", "Libya", "Mauritania", "France", "Germany", "Spain",
  "Italy", "United Kingdom", "Canada", "United States", "Turkey", "Saudi Arabia", "Qatar",
  "United Arab Emirates", "Malaysia", "China", "Other",
];

export const NATIONALITIES = [
  "Algerian", "Moroccan", "Tunisian", "Egyptian", "Libyan", "Mauritanian", "French", "Other",
];

// The 58 wilayas, in official order.
export const WILAYAS = [
  "Adrar", "Chlef", "Laghouat", "Oum El Bouaghi", "Batna", "Béjaïa", "Biskra", "Béchar", "Blida",
  "Bouira", "Tamanrasset", "Tébessa", "Tlemcen", "Tiaret", "Tizi Ouzou", "Algiers", "Djelfa",
  "Jijel", "Sétif", "Saïda", "Skikda", "Sidi Bel Abbès", "Annaba", "Guelma", "Constantine",
  "Médéa", "Mostaganem", "M'Sila", "Mascara", "Ouargla", "Oran", "El Bayadh", "Illizi",
  "Bordj Bou Arréridj", "Boumerdès", "El Tarf", "Tindouf", "Tissemsilt", "El Oued", "Khenchela",
  "Souk Ahras", "Tipaza", "Mila", "Aïn Defla", "Naâma", "Aïn Témouchent", "Ghardaïa", "Relizane",
  "Timimoun", "Bordj Badji Mokhtar", "Ouled Djellal", "Béni Abbès", "In Salah", "In Guezzam",
  "Touggourt", "Djanet", "El M'Ghair", "El Meniaa",
];

export function labelOf<T extends string | number>(options: readonly Option<T>[], value: T | null | undefined) {
  return options.find((o) => o.value === value)?.label ?? "";
}

export const STEPS = [
  { n: 1, slug: "about", title: "About you" },
  { n: 2, slug: "education", title: "Education & experience" },
  { n: 3, slug: "skills", title: "Skills & interests" },
  { n: 4, slug: "goals", title: "Goals & links" },
  { n: 5, slug: "alerts", title: "Alerts & consent" },
] as const;
