"use client";

// Hands an opportunity the AI read in chat over to the /submit form (this tab only).
const KEY = "oppradar-submit-prefill";

export function stashPrefill(values: Record<string, unknown>) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(values));
  } catch {
    /* storage blocked: the form simply starts empty */
  }
}

export function takePrefill(): Record<string, unknown> | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
