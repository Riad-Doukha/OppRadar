// Display helpers for opportunities (dashboard cards + detail page).

import type { Schemas } from "@/lib/api/client";

export type MyOpportunity = Schemas["MyOpportunity"];
export type OpportunityType = MyOpportunity["type"];
export type FeedTab = Schemas["MyOpportunityPage"]["tab"];

export const TYPE_LABELS: Record<OpportunityType, string> = {
  scholarship: "Scholarship",
  job: "Job",
  internship: "Internship",
  fellowship: "Fellowship",
  hackathon: "Hackathon",
  datathon: "Datathon",
  competition: "Competition",
  bootcamp: "Bootcamp",
  research: "Research",
  volunteer: "Volunteering",
  course: "Course",
  grant: "Grant",
  other: "Other",
};

const MODES: Record<string, string> = { remote: "Remote", hybrid: "Hybrid", onsite: "On-site" };
export const modeLabel = (mode: string | null) => (mode ? MODES[mode] ?? mode : null);

const LANGUAGES: Record<string, string> = { en: "English", fr: "French", ar: "Arabic" };
export const languageLabel = (code: string) => LANGUAGES[code] ?? code.toUpperCase();

const DAY = 24 * 60 * 60 * 1000;

/** Whole days from today to the deadline (negative once it has passed). */
export function daysLeft(deadline: string | null): number | null {
  if (!deadline) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((new Date(`${deadline}T00:00:00`).getTime() - today.getTime()) / DAY);
}

export function formatDate(iso: string, withYear = false) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", ...(withYear && { year: "numeric" }) });
}

/** "Closes 12 Mar · 8 days left" + whether it is urgent (≤ 7 days). */
export function deadlineText(deadline: string | null): { text: string; urgent: boolean } {
  const days = daysLeft(deadline);
  if (!deadline || days === null) return { text: "Rolling deadline", urgent: false };
  if (days < 0) return { text: `Closed ${formatDate(deadline)}`, urgent: false };
  const left = days === 0 ? "closes today" : days === 1 ? "1 day left" : `${days} days left`;
  return { text: `Closes ${formatDate(deadline)} · ${left}`, urgent: days <= 7 };
}

/** "Organizer · Algiers, Algeria · $5,000/mo" */
export function metaLine(o: MyOpportunity) {
  const place = [o.location, o.country].filter((p, i, all) => p && all.indexOf(p) === i).join(", ");
  return [o.organizer, place, o.funding].filter(Boolean).join(" · ");
}

export function sourceHost(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export const SCAM_FLAG_TEXT: Record<string, string> = {
  application_fee: "Asks for an application fee",
  bank_or_id_request: "Asks for bank or ID details",
  free_email_organizer: "Organizer uses a free email address",
  domain_mismatch: "Link domain doesn't match the organizer",
  unverifiable_organizer: "Organizer couldn't be verified",
  urgency_pressure: "Uses pressure or urgency tactics",
  too_good_to_be_true: "Offer looks too good to be true",
};
