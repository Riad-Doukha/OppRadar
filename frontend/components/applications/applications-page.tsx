"use client";

import { useQuery } from "@tanstack/react-query";

import { api, type Me } from "@/lib/api/client";

import { ApplicationList } from "./application-list";

/** Applications page: everything recorded through the Apply assistant. */
export function ApplicationsPage() {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  return (
    <div className="mx-auto max-w-[1112px]">
      <h1 className="font-display text-2xl font-bold tracking-[-0.5px] text-ink sm:text-[28px]">Applications</h1>
      <p className="pt-1 pb-5 text-sm text-body">Track where you applied and update the status when you hear back.</p>
      <ApplicationList readOnly={me.data?.is_demo ?? true} />
    </div>
  );
}
