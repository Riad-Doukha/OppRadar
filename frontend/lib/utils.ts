import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Only allow same-site relative redirects (`?next=/onboarding`), never `//evil.com`. */
export function safeNext(next: string | null | undefined, fallback = "/onboarding") {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : fallback;
}
