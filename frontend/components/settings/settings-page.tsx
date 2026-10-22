"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";

import { Alert } from "@/components/ui/alert";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { api, type Me } from "@/lib/api/client";
import { cn } from "@/lib/utils";

import { AccountTab } from "./account-tab";
import { AgentTab } from "./agent-tab";
import { NotificationsTab } from "./notifications-tab";
import { PrivacyTab } from "./privacy-tab";

const TABS = [
  { key: "account", label: "Account" },
  { key: "notifications", label: "Notifications" },
  { key: "privacy", label: "Privacy & AI" },
  { key: "agent", label: "Agent & sources" },
] as const;
type Tab = (typeof TABS)[number]["key"];

/** Settings (Figma): four tabs, the active one in the URL (?tab=…). */
export function SettingsPage() {
  const router = useRouter();
  const params = useSearchParams();
  const requested = params.get("tab");
  const tab: Tab = TABS.some((t) => t.key === requested) ? (requested as Tab) : "account";
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });

  return (
    <div className="mx-auto max-w-[1112px]">
      <h1 className="font-display text-2xl font-bold tracking-[-0.5px] text-ink sm:text-[28px]">Settings</h1>

      <div role="tablist" aria-label="Settings sections" className="mt-3.5 flex w-fit max-w-full gap-1.5 overflow-x-auto rounded-[14px] border border-line bg-[#f7f5fc] p-1.5">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            type="button"
            aria-selected={tab === t.key}
            onClick={() => router.replace(t.key === "account" ? "/settings" : `/settings?tab=${t.key}`, { scroll: false })}
            className={cn(
              "shrink-0 rounded-[10px] px-[18px] py-2.5 text-[14.5px] font-bold",
              tab === t.key ? "bg-surface text-brand shadow-[0_2px_4px_rgb(30_17_62/0.08)]" : "text-muted hover:text-ink",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {me.data?.is_demo && (
        <Alert tone="info" className="mt-4">
          You&apos;re viewing the read-only demo. Settings can&apos;t be changed here.
        </Alert>
      )}

      <div role="tabpanel" className="flex flex-col gap-4 pt-[18px]">
        {me.isError && <Alert>We couldn&apos;t load your settings: {me.error.message}</Alert>}
        {!me.data && !me.isError && <SettingsSkeleton />}
        {me.data && tab === "account" && <AccountTab me={me.data} />}
        {me.data && tab === "notifications" && <NotificationsTab me={me.data} />}
        {me.data && tab === "privacy" && <PrivacyTab me={me.data} />}
        {me.data && tab === "agent" && <AgentTab me={me.data} />}
      </div>
    </div>
  );
}

function SettingsSkeleton() {
  return (
    <Loading label="Loading settings…" className="flex flex-col gap-4">
      {[0, 1].map((i) => (
        <div key={i} className="rounded-card border border-line bg-surface px-7 py-6">
          <Skeleton className="h-3 w-24" />
          {[0, 1, 2].map((j) => (
            <div key={j} className="flex items-center gap-4 border-b border-line py-4 last:border-0">
              <div className="flex-1">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="mt-2 h-3.5 w-72 max-w-full" />
              </div>
              <Skeleton className="h-7 w-[50px] rounded-2xl" />
            </div>
          ))}
        </div>
      ))}
    </Loading>
  );
}
