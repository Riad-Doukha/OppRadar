"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import type { Me } from "@/lib/api/client";
import { useNotificationActions, useNotificationSummary } from "@/lib/notifications";

import { NotificationItem } from "./notification-item";

/** Header bell with the unread dot and the dropdown panel (Figma "Bell panel"). */
export function NotificationBell({ me }: { me?: Me }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const summary = useNotificationSummary();
  const { read } = useNotificationActions();
  const unread = summary.data?.unread ?? 0;
  const readOnly = me?.is_demo ?? true;

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  const n = me?.notifications;
  const channels = n ? [n.email_enabled && "Email", n.telegram_enabled && "Telegram"].filter(Boolean).join(" + ") || "in-app only" : "";

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
        className="relative flex size-10 items-center justify-center rounded-field hover:bg-page aria-expanded:bg-page"
      >
        <Image src="/icons/bell.svg" alt="" width={20} height={20} />
        {unread > 0 && <span className="absolute top-2 left-[23px] size-2 rounded-full border border-white bg-signal" />}
      </button>

      {open && (
        <div role="dialog" aria-label="Notifications" className="fixed inset-x-2 top-[70px] z-30 overflow-hidden rounded-card border border-line bg-surface shadow-float sm:absolute sm:inset-x-auto sm:top-auto sm:right-0 sm:mt-2 sm:w-[400px]">
          <div className="flex items-center gap-2 border-b border-line px-4 py-3.5">
            <p className="text-[15px] font-bold text-ink">Notifications</p>
            {unread > 0 && <span className="rounded-full bg-brand-soft px-2 py-0.5 font-mono text-xs font-bold text-brand-strong">{unread} new</span>}
            <span className="ml-auto flex gap-3 text-xs font-bold">
              {unread > 0 && !readOnly && (
                <button type="button" className="text-brand hover:text-brand-strong" onClick={() => read.mutate(undefined)}>
                  Mark all read
                </button>
              )}
              <Link href="/settings?tab=notifications" className="text-brand hover:text-brand-strong" onClick={() => setOpen(false)}>
                Preferences
              </Link>
            </span>
          </div>

          {summary.isPending && (
            <div className="flex flex-col gap-3 p-4" aria-busy>
              {[0, 1].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          )}
          {summary.data?.items.length === 0 && (
            <p className="px-5 py-8 text-center text-sm text-muted">
              You&apos;re all caught up. Deadline reminders for saved opportunities and, soon, new matches will show up here.
            </p>
          )}
          {summary.data && summary.data.items.length > 0 && (
            <ul className="max-h-[60vh] overflow-y-auto">
              {summary.data.items.slice(0, 4).map((item) => (
                <NotificationItem key={item.id} n={item} compact readOnly={readOnly} onNavigate={() => setOpen(false)} />
              ))}
            </ul>
          )}

          <div className="border-t border-line px-4 py-3 text-center">
            <Link href="/notifications" className="text-[13px] font-bold text-brand hover:text-brand-strong" onClick={() => setOpen(false)}>
              Open all notifications →
            </Link>
            {channels && <p className="pt-1 text-[11px] text-muted">Delivery: {channels} · per your rules</p>}
          </div>
        </div>
      )}
    </div>
  );
}
