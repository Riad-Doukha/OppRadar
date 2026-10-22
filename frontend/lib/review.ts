"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schemas } from "@/lib/api/client";

export type Reviewed = Schemas["ReviewedOpportunity"];
export type ReviewedPage = Schemas["ReviewedOpportunityPage"];
export type SubmissionIn = Schemas["SubmissionIn"];
export type AdminOpportunityIn = Schemas["AdminOpportunityIn"];
export type OpportunityPatch = Schemas["OpportunityPatch"];
export type ReviewIn = Schemas["ReviewIn"];
export type AdminStats = Schemas["AdminStats"];
export type TrustLevel = Reviewed["trust_level"];
export type ReviewStatus = Reviewed["review_status"];

export const TRUST_LEVELS: TrustLevel[] = ["verified", "likely_safe", "unknown", "suspicious", "scam"];

/** Badge colours per review status and trust level. */
export const REVIEW_TONE: Record<ReviewStatus, string> = {
  pending: "bg-warning-tint text-warning",
  approved: "bg-success-tint text-success",
  rejected: "bg-danger-soft text-danger",
};
export const TRUST_TONE: Record<TrustLevel, string> = {
  verified: "bg-success-tint text-success",
  likely_safe: "bg-success-tint text-success",
  unknown: "bg-page text-body",
  suspicious: "bg-warning-tint text-warning",
  scam: "bg-danger-soft text-danger",
};

// -- organisations -------------------------------------------------------------------- //
export function useMySubmissions() {
  return useQuery({ queryKey: ["submissions"], queryFn: () => api<Reviewed[]>("/me/submissions") });
}

export function useSubmit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SubmissionIn) => api<Reviewed>("/me/submissions", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["submissions"] });
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

// -- admins ------------------------------------------------------------------------------ //
export type AdminView = "queue" | "flagged" | "all";
const PAGE = 20;

export function useAdminStats() {
  return useQuery({ queryKey: ["admin", "stats"], queryFn: () => api<AdminStats>("/admin/stats") });
}

export function useAdminList(view: AdminView, q: string) {
  return useInfiniteQuery({
    queryKey: ["admin", "list", view, q],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => {
      const sp = new URLSearchParams({ limit: String(PAGE), offset: String(pageParam) });
      if (view === "queue") sp.set("status", "pending");
      if (view === "flagged") {
        sp.set("status", "approved");
        sp.append("trust", "suspicious");
        sp.append("trust", "scam");
      }
      if (q) sp.set("q", q);
      return api<ReviewedPage>(`/admin/opportunities?${sp}`);
    },
    getNextPageParam: (last) => (last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined),
  });
}

/** Every admin write refreshes the lists, the counts and the public feeds. */
function useAdminWrite<T>(fn: (vars: T) => Promise<unknown>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin"] });
      qc.invalidateQueries({ queryKey: ["feed"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export const useReview = () =>
  useAdminWrite(({ id, body }: { id: string; body: ReviewIn }) => api<Reviewed>(`/admin/opportunities/${id}/review`, { method: "POST", body: JSON.stringify(body) }));

export const useUpdateOpportunity = () =>
  useAdminWrite(({ id, body }: { id: string; body: OpportunityPatch }) => api<Reviewed>(`/admin/opportunities/${id}`, { method: "PATCH", body: JSON.stringify(body) }));

export const useCreateOpportunity = () =>
  useAdminWrite((body: AdminOpportunityIn) => api<Reviewed>("/admin/opportunities", { method: "POST", body: JSON.stringify(body) }));

export const useDeleteOpportunity = () => useAdminWrite((id: string) => api(`/admin/opportunities/${id}`, { method: "DELETE" }));
