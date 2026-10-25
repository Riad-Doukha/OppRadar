"use client";

import { useTranslations } from "next-intl";
import { useRef } from "react";

import { Button, ButtonLink } from "@/components/ui/button";
import { PLAN_FEATURES, PRICES, useDzd, usePremium } from "@/lib/premium";

import { PreviewPill } from "./coming-soon";

/** Sidebar teaser that opens the "Upgrade" modal (Figma upgrade modal, marked coming soon). */
export function UpgradeCard() {
  const ts = useTranslations("shell.upgrade");
  const t = useTranslations("premium");
  const tc = useTranslations("common");
  const dzd = useDzd();
  const dialog = useRef<HTMLDialogElement>(null);
  const reservation = usePremium().data?.reservation;

  return (
    <>
      <div className="rounded-card bg-night p-4 text-white">
        <p className="font-mono text-[10px] tracking-[1px] text-signal uppercase">{ts("eyebrow")}</p>
        <p className="pt-1.5 text-sm font-bold">{reservation ? ts("inLine", { position: reservation.position }) : ts("pitch")}</p>
        <button type="button" onClick={() => dialog.current?.showModal()} className="mt-3 text-xs font-bold text-signal underline">
          {reservation ? ts("seeComing") : ts("learnMore")}
        </button>
      </div>

      <dialog
        ref={dialog}
        aria-labelledby="upgrade-title"
        onClick={(e) => e.target === dialog.current && dialog.current.close()}
        className="m-auto w-[calc(100%-2rem)] max-w-[440px] rounded-card bg-surface p-0 shadow-float backdrop:bg-night/70"
      >
        <div className="flex flex-col gap-4 p-6">
          <div className="flex items-start justify-between gap-3">
            <PreviewPill>{t("modal.pill")}</PreviewPill>
            <button type="button" onClick={() => dialog.current?.close()} aria-label={tc("close")} className="text-xl leading-none text-muted hover:text-ink">
              ×
            </button>
          </div>
          <h2 id="upgrade-title" className="font-display text-2xl font-bold text-ink">
            {t("modal.title")}
          </h2>
          <p className="text-sm text-body">
            {t("modal.body", { price: dzd(PRICES.premium.monthly) })}
          </p>
          <ul className="flex flex-col gap-1.5 text-sm text-ink">
            {PLAN_FEATURES.premium.slice(0, 5).map((f) => (
              <li key={f}>○ {t(`features.premium.${f}`)}</li>
            ))}
          </ul>
          <p className="text-xs text-muted">{t("modal.free")}</p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <ButtonLink href={reservation ? "/premium/reserved" : "/premium"} size="md" className="flex-1" onClick={() => dialog.current?.close()}>
              {reservation ? t("modal.mine") : t("modal.plans")}
            </ButtonLink>
            <Button variant="outline" size="md" className="flex-1" onClick={() => dialog.current?.close()}>
              {t("modal.later")}
            </Button>
          </div>
        </div>
      </dialog>
    </>
  );
}
