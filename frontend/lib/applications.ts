"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schemas } from "@/lib/api/client";

export type Application = Schemas["ApplicationOut"];
export type ApplicationStatus = Application["status"];

export const STATUS: Record<ApplicationStatus, { label: string; tone: string }> = {
  draft: { label: "Draft", tone: "bg-page text-body" },
  submitted: { label: "Submitted", tone: "bg-brand-soft text-brand-strong" },
  accepted: { label: "Accepted", tone: "bg-[#ecfdf5] text-success" },
  rejected: { label: "Not selected", tone: "bg-danger-soft text-danger" },
  withdrawn: { label: "Withdrawn", tone: "bg-page text-muted" },
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
