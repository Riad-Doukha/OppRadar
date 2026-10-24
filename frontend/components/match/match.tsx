"use client";

import { useTranslations } from "next-intl";

import type { Schemas } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type Match = Schemas["MatchInfo"];

/** "82% match" — strong (purple) from 70, else neutral. */
export function MatchScore({ match, className }: { match: Match; className?: string }) {
  const t = useTranslations("opportunity.match");
  const score = Math.round(match.score);
  return (
    <span className={cn("flex h-7 shrink-0 items-center rounded-full px-3 font-mono text-xs font-bold", score >= 70 ? "bg-brand text-white" : "bg-brand-soft text-brand-strong", className)}>
      {t("score", { score })}
    </span>
  );
}

/** "Why you're seeing this" + "Still missing" (AI text is rendered as plain text). */
export function MatchReasons({ match, limit, className }: { match: Match; limit?: number; className?: string }) {
  const t = useTranslations("opportunity.match");
  const reasons = limit ? match.top_reasons.slice(0, limit) : match.top_reasons;
  const missing = limit ? match.unmet_requirements.slice(0, 1) : match.unmet_requirements;
  if (!reasons.length && !missing.length) return null;
  return (
    <div className={cn("flex flex-col gap-1 text-[13px]", className)}>
      {reasons.length > 0 && (
        <p className="sr-only">{t("why")}</p>
      )}
      {reasons.map((r) => (
        <p key={r} className="flex gap-1.5 text-body">
          <span className="text-success" aria-hidden>
            ✓
          </span>
          {r}
        </p>
      ))}
      {missing.map((r) => (
        <p key={r} className="flex gap-1.5 text-warning">
          <span aria-hidden>!</span>
          <span>
            <span className="sr-only">{t("missing")}: </span>
            {r}
          </span>
        </p>
      ))}
      {!limit && match.reasons_source === "llm" && <p className="pt-1 text-[11px] text-muted">{t("byAi")}</p>}
    </div>
  );
}

const STATUS_TONE = { met: "bg-success-tint text-success", unmet: "bg-danger-soft text-danger", unknown: "bg-page text-muted" } as const;

/** The matcher's per-requirement checklist (detail page). */
export function Criteria({ match }: { match: Match }) {
  const t = useTranslations("opportunity.match");
  if (!match.criteria.length) return null;
  return (
    <ul className="mt-2 divide-y divide-line border-y border-line">
      {match.criteria.map((c) => (
        <li key={c.text} className="flex items-start justify-between gap-3 py-3">
          <span className="min-w-0">
            <span className="block text-[15px] text-ink">{c.text}</span>
            {c.evidence && <span className="block pt-0.5 text-xs text-muted">{c.evidence}</span>}
          </span>
          <span className={cn("shrink-0 rounded-full px-3 py-1 text-xs font-bold", STATUS_TONE[c.status])}>{t(c.status)}</span>
        </li>
      ))}
    </ul>
  );
}
