"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schemas } from "@/lib/api/client";

export type Notification = Schemas["NotificationOut"];
export type NotificationList = Schemas["NotificationList"];
export type NotificationTab = "all" | "matches" | "deadlines" | "applications" | "system";

/** Icon + tinted tile per kind (Figma Notifications page). */
export const KIND_STYLE: Record<Notification["kind"], { icon: string; tile: string; grey?: boolean }> = {
  match: { icon: "notif-match", tile: "bg-brand-soft" },
  deadline: { icon: "notif-deadline", tile: "bg-warning-tint" },
  application: { icon: "notif-application", tile: "bg-success-tint" },
  digest: { icon: "notif-digest", tile: "bg-page", grey: true },
  tip: { icon: "notif-tip", tile: "bg-page", grey: true },
  security: { icon: "notif-security", tile: "bg-page", grey: true },
  system: { icon: "notif-digest", tile: "bg-page", grey: true },
};

/** "09:41" today, "Yesterday", "Mon" this week, else "12 Mar" (in `locale`). */
export function when(iso: string, locale: string, yesterday: string) {
  const d = new Date(iso);
  const now = new Date();
  const days = Math.floor((new Date(now.toDateString()).getTime() - new Date(d.toDateString()).getTime()) / 86_400_000);
  if (days === 0) return d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
  if (days === 1) return yesterday;
  if (days < 7) return d.toLocaleDateString(locale, { weekday: "short" });
  return d.toLocaleDateString(locale, { day: "numeric", month: "short" });
}

/** Latest few + unread count, for the bell and the sidebar badge (refreshes every minute). */
export function useNotificationSummary() {
  return useQuery({
    queryKey: ["notifications", "summary"],
    queryFn: () => api<NotificationList>("/me/notifications?limit=5"),
    refetchInterval: 60_000,
  });
}

export function useNotificationActions() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["notifications"] });
  const read = useMutation({
    mutationFn: (ids?: string[]) => api<NotificationList>("/me/notifications/read", { method: "POST", body: JSON.stringify(ids ? { ids } : {}) }),
    onSuccess: refresh,
  });
  const dismiss = useMutation({
    mutationFn: (id: string) => api(`/me/notifications/${id}`, { method: "DELETE" }),
    onSuccess: refresh,
  });
  return { read, dismiss };
}
