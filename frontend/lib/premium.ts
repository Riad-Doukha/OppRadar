"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useCallback } from "react";

import { intlLocale, type Locale } from "@/i18n/config";
import { api, type Schemas } from "@/lib/api/client";

export type PremiumStatus = Schemas["PremiumStatus"];
export type ReservationIn = Schemas["ReservationIn"];
export type Plan = NonNullable<ReservationIn["plan"]>;
export type Billing = NonNullable<ReservationIn["billing"]>;
export type PaymentMethod = NonNullable<ReservationIn["payment_method"]>;

/** Planned prices from the design — shown as "planned", nothing is charged before launch. */
export const PRICES: Record<Plan, Record<Billing, number>> = {
  premium: { monthly: 990, yearly: 8900 },
  clubs: { monthly: 3900, yearly: 35100 },
};

/** Labels are premium.methods.<value> and <value>_hint. */
export const PAYMENT_METHODS: PaymentMethod[] = ["cib", "edahabia", "baridimob", "ccp"];

/** What each plan will include (premium.features.<plan>.<key>); all Premium/Clubs features are coming soon. */
export const PLAN_FEATURES = {
  free: ["f1", "f2", "f3", "f4", "f5"],
  premium: ["f1", "f2", "f3", "f4", "f5", "f6", "f7"],
  clubs: ["f1", "f2", "f3", "f4", "f5"],
} as const;

/** Comparison table: row → cell per plan. Cells are premium.compare.cells.<key>, or literal symbols/numbers. */
type Cell = "perDay3" | "perDay5" | "every30" | "unlimited" | "instant" | "perSeat" | "basic" | "deep" | "calendar" | "✓" | "—" | "1" | "5";
export const COMPARE: { row: "scans" | "checks" | "cv" | "drafts" | "explain" | "reminders" | "shared"; free: Cell; premium: Cell; clubs: Cell }[] = [
  { row: "scans", free: "perDay3", premium: "every30", clubs: "every30" },
  { row: "checks", free: "perDay5", premium: "unlimited", clubs: "unlimited" },
  { row: "cv", free: "✓", premium: "instant", clubs: "instant" },
  { row: "drafts", free: "1", premium: "5", clubs: "perSeat" },
  { row: "explain", free: "basic", premium: "deep", clubs: "deep" },
  { row: "reminders", free: "✓", premium: "calendar", clubs: "calendar" },
  { row: "shared", free: "—", premium: "—", clubs: "✓" },
];
export const isLiteralCell = (c: Cell): c is "✓" | "—" | "1" | "5" => ["✓", "—", "1", "5"].includes(c);

/** Amount with the locale's grouping (Latin digits), e.g. "8,900" / "8 900". */
export function useAmount() {
  const locale = intlLocale(useLocale() as Locale);
  return useCallback((n: number) => n.toLocaleString(locale), [locale]);
}

/** "8,900 DZD" / "8 900 DZD" / "8 900 دج". */
export function useDzd() {
  const t = useTranslations("premium");
  const amount = useAmount();
  return useCallback((n: number) => t("dzd", { amount: amount(n) }), [t, amount]);
}

export function usePremium() {
  return useQuery({ queryKey: ["premium"], queryFn: () => api<PremiumStatus>("/me/premium") });
}

export function useReserve() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ReservationIn) => api<PremiumStatus>("/me/premium/reservation", { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: (s) => qc.setQueryData(["premium"], s),
  });
}

export function useCancelReservation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<PremiumStatus>("/me/premium/reservation", { method: "DELETE" }),
    onSuccess: (s) => qc.setQueryData(["premium"], s),
  });
}
