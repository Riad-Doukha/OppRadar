"use client";

import { useQuery } from "@tanstack/react-query";
import { useTranslations } from "next-intl";

import { api, type Me } from "@/lib/api/client";

import { ApplicationList } from "./application-list";

/** Applications page: everything recorded through the Apply assistant. */
export function ApplicationsPage() {
  const t = useTranslations("applications");
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  return (
    <div className="mx-auto max-w-[1112px]">
      <h1 className="font-display text-2xl font-bold tracking-[-0.5px] text-ink sm:text-[28px]">{t("title")}</h1>
      <p className="pt-1 pb-5 text-sm text-body">{t("subtitle")}</p>
      <ApplicationList readOnly={me.data?.is_demo ?? true} />
    </div>
  );
}
