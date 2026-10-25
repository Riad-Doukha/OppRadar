// Onboarding state derived from GET /me (onboarding.completed_at + missing).

import type { Me } from "@/lib/api/client";
import { STEPS } from "@/lib/onboarding/options";

/** Setup is complete when it was finished and no required field has been emptied since. */
export function isComplete(me: Me) {
  return Boolean(me.onboarding.completed_at) && me.onboarding.missing.length === 0;
}

/** Steps with no required field missing (the API's missing keys are "step.field"). */
export function stepsDone(me: Me) {
  return STEPS.filter((s) => !me.onboarding.missing.some((m) => m.startsWith(`${s.slug}.`))).length;
}

/** First step that still has a required field missing. */
export function firstIncompleteStep(me: Me) {
  return STEPS.find((s) => me.onboarding.missing.some((m) => m.startsWith(`${s.slug}.`)))?.n ?? 5;
}
