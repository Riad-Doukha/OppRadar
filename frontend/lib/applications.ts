"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schemas } from "@/lib/api/client";

export type Application = Schemas["ApplicationOut"];
export type ApplicationStatus = Application["status"];

/** Badge colours per status; labels are applications.status.<status>. */
export const STATUS: Record<ApplicationStatus, { tone: string }> = {
  draft: { tone: "bg-page text-body" },
  submitted: { tone: "bg-brand-soft text-brand-strong" },
  accepted: { tone: "bg-success-tint text-success" },
  rejected: { tone: "bg-danger-soft text-danger" },
  withdrawn: { tone: "bg-page text-muted" },
};

export function useApplications() {
  return useQuery({ queryKey: ["applications"], queryFn: () => api<Application[]>("/me/applications") });
}

/** Create/update the application for an opportunity; refreshes lists, counts and the bell. */
export function useSaveApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ opportunityId, body }: { opportunityId: string; body: Partial<Pick<Application, "status" | "reference" | "notes">> }) =>
      api<Application>(`/me/applications/${opportunityId}`, { method: "PUT", body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

export function useRemoveApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (opportunityId: string) => api(`/me/applications/${opportunityId}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["applications"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
