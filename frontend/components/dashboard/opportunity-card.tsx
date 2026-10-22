"use client";

import Image from "next/image";
import Link from "next/link";

import { Button, ButtonLink } from "@/components/ui/button";
import { Pill } from "@/components/ui/inputs";
import { useOpportunityAction } from "@/lib/hooks/use-opportunity-actions";
import { TYPE_LABELS, deadlineText, metaLine, modeLabel, sourceHost, type MyOpportunity } from "@/lib/opportunities";
import { cn } from "@/lib/utils";

/**
 * One card of the dashboard feed. The design's match ring and "Eligible"
 * badge appear here once the AI matcher provides them; until then the card
 * shows the facts we have and a safety badge for flagged sources.
 */
export function OpportunityCard({ item, readOnly }: { item: MyOpportunity; readOnly: boolean }) {
  const action = useOpportunityAction();
  const deadline = deadlineText(item.deadline);
  const flagged = item.trust_level === "suspicious" || item.trust_level === "scam";
  const mode = modeLabel(item.mode);
  const busy = action.isPending;

  return (
    <article className="rounded-card border border-line bg-surface p-[22px] shadow-[0_1px_1.5px_rgb(30_17_62/0.05)]">
      <div className="flex flex-wrap items-center gap-2">
        <Pill className="h-7 text-xs">{TYPE_LABELS[item.type]}</Pill>
        {item.is_new && (
          <span className="flex h-7 items-center gap-1.5 rounded-full bg-signal px-3 text-xs font-bold text-ink">
            <Image src="/icons/sparkle-dark.svg" alt="" width={13} height={13} />
            New
          </span>
        )}
        {item.trust_level === "verified" && (
          <span className="flex h-7 items-center gap-1.5 rounded-full bg-[#ecfdf5] px-3 text-[13px] font-bold text-success">
            <Image src="/icons/check-circle-green-14.svg" alt="" width={14} height={14} />
            Verified source
          </span>
        )}
        {flagged && (
          <span className="flex h-7 items-center gap-1.5 rounded-full bg-danger-soft px-3 text-[13px] font-bold text-danger">
            <Image src="/icons/x-circle-red.svg" alt="" width={14} height={14} />
            {item.trust_level === "scam" ? "Likely scam" : "Check this source"}
          </span>
        )}
      </div>

      <h3 className="pt-2.5 text-lg leading-snug font-bold text-ink">
        <Link href={`/opportunities/${item.id}`} className="hover:text-brand-strong">
          {item.title}
        </Link>
      </h3>
      <p className="pt-1 text-[13px] text-muted">{metaLine(item)}</p>
      {item.summary && (
        <p className="flex gap-1.5 pt-2 text-sm text-body">
          <span className="text-brand" aria-hidden>
            –
          </span>
          <span className="line-clamp-2">{item.summary}</span>
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2 pt-3.5">
        <span className={cn("flex items-center gap-1.5 text-[13px] font-bold", deadline.urgent ? "text-warning" : "text-ink")}>
          <Image src={deadline.urgent ? "/icons/clock-orange.svg" : "/icons/clock-dark.svg"} alt="" width={15} height={15} />
          {deadline.text}
        </span>
        {mode && <Pill muted className="h-[26px] text-xs">{mode}</Pill>}
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
        <span className="font-mono text-xs text-muted">source: {sourceHost(item.url) || item.source}</span>
        <div className="flex gap-2.5">
          {!readOnly && (
            <Button
              variant="outline"
              className="h-10 text-sm"
              disabled={busy}
              aria-pressed={item.saved}
              onClick={() => action.mutate({ id: item.id, flag: "saved", on: !item.saved })}
            >
              <Image src="/icons/bookmark-purple.svg" alt="" width={15} height={15} />
              {item.saved ? "Saved" : "Save"}
            </Button>
          )}
          <ButtonLink href={`/opportunities/${item.id}`} className="h-10 text-sm">
            View details
          </ButtonLink>
        </div>
      </div>
      {action.isError && <p className="pt-2 text-xs text-danger">Couldn&apos;t update. Try again.</p>}
    </article>
  );
}
