// Helpers that turn wizard form state into PATCH bodies the API accepts while
// the user is still typing (autosave must never send an invalid value).

/** "" -> null so a cleared optional field is cleared on the server. */
export const orNull = (v: string) => (v.trim() ? v.trim() : null);

/** Integer within [min, max], or null when empty, or undefined (don't send) when invalid. */
export function intIn(v: string, min: number, max: number): number | null | undefined {
  if (!v.trim()) return null;
  const n = Number(v);
  return Number.isInteger(n) && n >= min && n <= max ? n : undefined;
}

/** Drop keys whose value is undefined (= "don't send"). */
export function defined<T extends object>(o: T): Partial<T> {
  return Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined)) as Partial<T>;
}

/** Drop null / "" / [] too — for applying CV prefill without wiping typed values. */
export function filled<T extends object>(o: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(o).filter(([, v]) => v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && v.length === 0)),
  ) as Partial<T>;
}
