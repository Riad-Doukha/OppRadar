"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";

import { Alert } from "@/components/ui/alert";
import { Button, ButtonLink } from "@/components/ui/button";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { api, type Me } from "@/lib/api/client";
import { useNotificationActions, type NotificationList, type NotificationTab } from "@/lib/notifications";
import { cn } from "@/lib/utils";

import { NotificationItem } from "./notification-item";

const TABS: { key: NotificationTab; label: string }[] = [
  { key: "all", label: "All" },
  { key: "matches", label: "Matches" },
  { key: "deadlines", label: "Deadlines" },
  { key: "applications", label: "Applications" },
  { key: "system", label: "System" },
];

const EMPTY: Record<NotificationTab, string> = {
  all: "Nothing yet. You'll get deadline reminders for saved opportunities here, and new matches once matching launches.",
  matches: "Match alerts arrive once matching launches.",
  deadlines: "Save an opportunity and you'll be reminded 3 days before it closes.",
  applications: "Application updates arrive with the apply assistant.",
  system: "Weekly summaries, profile tips and account messages show up here.",
};

/** Notifications page (Figma): tabs, list, Mark all read, Preferences. */
export function NotificationsPage() {
  const router = useRouter();
  const params = useSearchParams();
  const requested = params.get("tab") as NotificationTab | null;
  const tab: NotificationTab = TABS.some((t) => t.key === requested) ? requested! : "all";
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  const list = useQuery({ queryKey: ["notifications", "tab", tab], queryFn: () => api<NotificationList>(`/me/notifications?tab=${tab}`) });
  const { read } = useNotificationActions();
  const readOnly = me.data?.is_demo ?? true;
  const unread = list.data?.unread ?? 0;

  return (
    <div className="mx-auto max-w-[1112px]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-2xl font-bold tracking-[-0.5px] text-ink sm:text-[28px]">Notifications</h1>
        <div className="flex gap-2.5">
          {!readOnly && (
            <Button variant="ghost" className="h-10 text-sm" disabled={!unread || read.isPending} onClick={() => read.mutate(undefined)}>
              Mark all read
            </Button>
          )}
          <ButtonLink href="/settings?tab=notifications" variant="outline" className="h-10 text-sm">
            Preferences
          </ButtonLink>
        </div>
      </div>

      <div role="tablist" aria-label="Notification types" className="mt-3.5 flex gap-7 overflow-x-auto border-b border-line">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            type="button"
            aria-selected={tab === t.key}
            onClick={() => router.replace(t.key === "all" ? "/notifications" : `/notifications?tab=${t.key}`, { scroll: false })}
            className={cn("flex shrink-0 items-center gap-1.5 border-b-[3px] pt-3 pb-3 text-[15px]", tab === t.key ? "border-brand font-bold text-ink" : "border-transparent font-medium text-muted hover:text-ink")}
          >
            {t.label}
            {t.key === "all" && unread > 0 && <span className="rounded-full bg-brand-soft px-[7px] py-0.5 font-mono text-[11px] font-bold text-brand-strong">{unread}</span>}
          </button>
        ))}
      </div>

      <div className="pt-4">
        {list.isError && <Alert>We couldn&apos;t load notifications: {list.error.message}</Alert>}
        {list.isPending && (
          <Loading label="Loading notifications…" className="overflow-hidden rounded-card border border-line bg-surface">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex gap-3.5 border-b border-line px-5 py-4 last:border-0">
                <Skeleton className="size-[38px] rounded-[11px]" />
                <div className="flex-1">
                  <Skeleton className="h-4 w-2/3" />
                  <Skeleton className="mt-2 h-3.5 w-full" />
                </div>
              </div>
            ))}
          </Loading>
        )}
        {list.data?.items.length === 0 && (
          <div className="rounded-card border border-dashed border-line bg-surface px-6 py-10 text-center">
            <p className="text-base font-bold text-ink">You&apos;re all caught up</p>
            <p className="mx-auto max-w-md pt-1.5 text-sm text-muted">{EMPTY[tab]}</p>
          </div>
        )}
        {list.data && list.data.items.length > 0 && (
          <ul className="overflow-hidden rounded-card border border-line bg-surface shadow-[0_1px_3px_rgb(30_17_62/0.05)]">
            {list.data.items.map((n) => <NotificationItem key={n.id} n={n} readOnly={readOnly} />)}
          </ul>
        )}
        <p className="pt-3.5 text-center text-xs text-muted">Notifications older than 30 days are archived automatically.</p>
      </div>
    </div>
  );
}
