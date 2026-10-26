"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Logo } from "@/components/brand/logo";
import { Alert } from "@/components/ui/alert";
import { ButtonLink } from "@/components/ui/button";
import { intlLocale, type Locale } from "@/i18n/config";
import { api, type Me, type Schemas } from "@/lib/api/client";

type Line = { at: string; text: string };

// One scan per visit, shared by React's dev double-mount; cleared once it ends
// so a later visit to /scan starts a new one.
let running: Promise<unknown> | null = null;
function startScan(onDone: () => void) {
  running ??= api("/me/agent/start", { method: "POST" }).finally(() => {
    running = null;
    onDone(); // the dashboard may already be open: refresh it with the results
  });
  return running;
}
const clock = (locale: string) => new Date().toLocaleTimeString(locale, { hour12: false });

/**
 * "Your agent is starting its first scan" (Figma). Every line is a real step:
 * start the agent, load the profile, count what fits — then go to the
 * dashboard.
 * The user can leave for the dashboard at any time: the scan carries on.
 */
export function FirstScan() {
  const t = useTranslations("dashboard.scan");
  const locale = intlLocale(useLocale() as Locale);
  const router = useRouter();
  const qc = useQueryClient();
  const [lines, setLines] = useState<Line[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const say = async (text: string) => {
      if (cancelled) return;
      setLines((l) => [...l, { at: clock(locale), text }]);
      await new Promise((r) => setTimeout(r, 700)); // keep each step readable
    };
    (async () => {
      try {
        const me = await api<Me>("/me");
        // Start right away, even if the user has already left for the dashboard:
        // the scan runs on the server; the log below only narrates it.
        const scan = me.is_demo ? Promise.resolve() : startScan(() => {
          for (const key of ["dashboard", "feed", "notifications"]) qc.invalidateQueries({ queryKey: [key] });
        });
        await say(t("loaded", { name: me.full_name || me.email }));
        await scan;
        await say(t("started"));
        const stats = await api<Schemas["DashboardStats"]>("/me/dashboard");
        await say(t("fit", { count: stats.for_you }));
        await say(t("close", { count: stats.closing_this_week }));
        await say(t("deadlineSort"));
        if (cancelled) return;
        setDone(true);
        setTimeout(() => !cancelled && router.push("/dashboard"), 1500);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
    // Runs once: the scan log must not restart when the language object identity changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  return (
    <div className="min-h-dvh bg-page">
      <header className="flex h-[60px] items-center border-b border-line bg-surface px-4 md:h-[68px] md:px-10">
        <Logo href={null} />
      </header>
      <main className="flex flex-col items-center px-4 py-12 text-center md:py-20">
        <div className="radar-disc relative aspect-square w-60 overflow-hidden rounded-full md:w-80" aria-hidden>
          <div className="absolute inset-[6.9%] rounded-full border border-white/25">
            <div className="absolute inset-[20%] rounded-full border border-white/25" />
            <div className="absolute inset-[40%] rounded-full border border-white/25" />
            <div className="absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 bg-white/25" />
            <div className="absolute inset-x-0 top-1/2 h-0.5 -translate-y-1/2 bg-white/25" />
          </div>
          <div className="radar-sweep absolute inset-0 rounded-full" />
          <span className="radar-blip absolute top-[27.5%] start-[65%] size-4 rounded-full bg-signal shadow-[0_0_0_6px_rgb(250_252_82/0.35)]" />
          <span className="radar-blip absolute top-[64%] start-[28.75%] size-[11px] rounded-full bg-signal shadow-[0_0_0_5px_rgb(250_252_82/0.28)] [animation-delay:0.8s]" />
        </div>

        <h1 className="pt-9 font-display text-2xl font-bold tracking-[-0.5px] text-ink md:text-[28px]">{t("title")}</h1>
        <p className="max-w-[460px] pt-2.5 text-base leading-6 text-body">
          {t("body")}
        </p>

        <div className="mt-7 w-full max-w-[520px] rounded-field bg-night px-[18px] py-4 text-start font-mono text-xs leading-6" aria-live="polite">
          {lines.map((l, i) => (
            <p key={i} className={i === lines.length - 1 && !done ? "text-[#d9d2ea]" : "text-[#8b7fb0]"}>
              {l.at} <span className="inline-block rtl:-scale-x-100">→</span> {l.text}
            </p>
          ))}
          {!done && !error && (
            <p className="flex items-center gap-2 text-[#d9d2ea]">
              {clock(locale)} <span className="inline-block rtl:-scale-x-100">→</span> <span className="size-[7px] animate-pulse rounded-full bg-signal" /> {t("working")}
            </p>
          )}
        </div>

        {error ? (
          <div className="mt-6 w-full max-w-[520px]">
            <Alert>{t("error", { error })}</Alert>
            <ButtonLink href="/dashboard" size="md" className="mt-4">
              {t("toDashboard")}
            </ButtonLink>
          </div>
        ) : (
          <>
            <p className="flex items-center gap-3 pt-6 text-sm text-body">
              <span className="size-5 animate-spin rounded-full border-2 border-brand-soft border-t-brand" aria-hidden />
              {done ? t("taking") : t("starting")}
            </p>
            {!done && (
              <ButtonLink href="/dashboard" variant="outline" size="md" className="mt-5">
                {t("background")}
              </ButtonLink>
            )}
          </>
        )}
      </main>
    </div>
  );
}
