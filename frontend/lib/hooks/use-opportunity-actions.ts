"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api/client";
import type { MyOpportunity } from "@/lib/opportunities";

type Flag = "saved" | "dismissed";

/** Save / unsave and Not interested, then refresh the feed + counts. */
export function useOpportunityAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, flag, on }: { id: string; flag: Flag; on: boolean }) =>
      api<MyOpportunity>(`/me/opportunities/${id}/${flag}`, { method: on ? "PUT" : "DELETE" }),
    onSuccess: (item) => {
      qc.setQueryData(["opportunity", item.id], item);
      qc.invalidateQueries({ queryKey: ["feed"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
