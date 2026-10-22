"use client";

import Image from "next/image";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { intlLocale, type Locale } from "@/i18n/config";
import { useOpportunityAction } from "@/lib/hooks/use-opportunity-actions";
import { KIND_STYLE, useNotificationActions, when, type Notification } from "@/lib/notifications";
import { cn } from "@/lib/utils";

/**
 * One notification row. `compact` is the bell dropdown version (fewer
 * actions, tighter spacing). Opening a notification marks it read.
 */
export function NotificationItem({ n, compact, readOnly, onNavigate }: { n: Notification; compact?: boolean; readOnly: boolean; onNavigate?: () => void }) {
  const t = useTranslations("notifications.item");
  const tc = useTranslations("common.time");
  const locale = intlLocale(useLocale() as Locale);
  const router = useRouter();
  const { read, dismiss } = useNotificationActions();
  const save = useOpportunityAction();
  const style = KIND_STYLE[n.kind];

  function open(href: string) {
    if (!n.read && !readOnly) read.mutate([n.id]);
    onNavigate?.();
    router.push(href);
  }

  const actions = (() => {
    if (readOnly) return null;
    if (n.kind === "deadline" && n.action_url)
      return (
        <>
          <Button className="h-[34px] text-[13px]" onClick={() => open(n.action_url!)}>
            {t("applyNow")}
          </Button>
          {!n.read && (
            <Button variant="ghost" className="h-[34px] text-[13px]" onClick={() => read.mutate([n.id])}>
              {compact ? t("later") : t("remindLater")}
            </Button>
          )}
        </>
      );
    if (n.kind === "match" && n.action_url)
      return (
        <>
          <Button className="h-[34px] text-[13px]" onClick={() => open(n.action_url!)}>
            {t("viewMatch")}
          </Button>
          {!compact && n.opportunity_id && (
            <Button variant="outline" className="h-[34px] text-[13px]" onClick={() => save.mutate({ id: n.opportunity_id!, flag: "saved", on: true })} disabled={save.isPending}>
              {t("save")}
            </Button>
          )}
          <Button variant="ghost" className="h-[34px] text-[13px]" onClick={() => dismiss.mutate(n.id)}>
            {t("dismiss")}
          </Button>
        </>
      );
    if (!compact && n.action_url)
      return (
        <Button variant="outline" className="h-[34px] text-[13px]" onClick={() => open(n.action_url!)}>
          {n.kind === "tip" ? t("improveProfile") : n.kind === "application" ? t("openApplications") : t("open")}
        </Button>
      );
    return null;
  })();

  return (
    <li className={cn("flex items-start gap-3.5 border-b border-line last:border-b-0", compact ? "px-4 py-3.5" : "px-5 py-4", !n.read && "bg-page")}>
      <span className={cn("flex shrink-0 items-center justify-center rounded-[11px]", compact ? "size-8" : "size-[38px]", style.tile)}>
        <Image src={`/icons/${style.icon}.svg`} alt="" width={compact ? 16 : 19} height={compact ? 16 : 19} className={style.grey ? "icon-adapt" : undefined} />
      </span>
      <div className="min-w-0 flex-1">
        {n.action_url ? (
          <Link href={n.action_url} onClick={(e) => (e.preventDefault(), open(n.action_url!))} className={cn("block font-bold hover:text-brand-strong", compact ? "text-sm" : "text-[15px]", n.read ? "text-body" : "text-ink")}>
            {n.title}
          </Link>
        ) : (
          <p className={cn("font-bold", compact ? "text-sm" : "text-[15px]", n.read ? "text-body" : "text-ink")}>{n.title}</p>
        )}
        {n.body && <p className={cn("pt-[3px] text-body", compact ? "line-clamp-2 text-xs" : "text-sm")}>{n.body}</p>}
        {actions && <div className="flex flex-wrap gap-2 pt-[9px]">{actions}</div>}
      </div>
      <span className="shrink-0 font-mono text-xs text-muted">{when(n.created_at, locale, tc("yesterday"))}</span>
      {!n.read && <span className="mt-1.5 size-[9px] shrink-0 rounded-full bg-brand" aria-label={t("unread")} />}
    </li>
  );
}
