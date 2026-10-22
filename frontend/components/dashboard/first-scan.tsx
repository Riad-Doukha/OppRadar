"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Logo } from "@/components/brand/logo";
import { Alert } from "@/components/ui/alert";
import { ButtonLink } from "@/components/ui/button";
import { api, type Me, type Schemas } from "@/lib/api/client";

type Line = { at: string; text: string };
const clock = () => new Date().toLocaleTimeString("en-GB", { hour12: false });

/**
 * "Your agent is starting its first scan" (Figma). Every line is a real step:
 * start the agent, load the profile, count what fits — then go to the
 * dashboard. Match scores join once the AI matcher ships.
 */
export function FirstScan() {
  const router = useRouter();
  const [lines, setLines] = useState<Line[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const say = async (text: string) => {
      if (cancelled) return;
      setLines((l) => [...l, { at: clock(), text }]);
      await new Promise((r) => setTimeout(r, 700)); // keep each step readable
    };
    (async () => {
      try {
        const me = await api<Me>("/me");
        await say(`Loaded profile: ${me.full_name || me.email}`);
        if (!me.is_demo) await api("/me/agent/start", { method: "POST" });
        await say("Agent started");
        const stats = await api<Schemas["DashboardStats"]>("/me/dashboard");
        await say(`${stats.for_you} open opportunities fit the types you chose`);
        await say(`${stats.closing_this_week} close in the next 7 days`);
        await say("Match scores arrive when matching launches — sorting by deadline for now");
        if (cancelled) return;
        setDone(true);
        setTimeout(() => !cancelled && router.push("/dashboard"), 1500);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Something went wrong.");
      }
    })();
    return () => {
      cancelled = true;
    };
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
          <span className="radar-blip absolute top-[27.5%] left-[65%] size-4 rounded-full bg-signal shadow-[0_0_0_6px_rgb(250_252_82/0.35)]" />
          <span className="radar-blip absolute top-[64%] left-[28.75%] size-[11px] rounded-full bg-signal shadow-[0_0_0_5px_rgb(250_252_82/0.28)] [animation-delay:0.8s]" />
        </div>

        <h1 className="pt-9 font-display text-2xl font-bold tracking-[-0.5px] text-ink md:text-[28px]">Your agent is starting its first scan</h1>
        <p className="max-w-[460px] pt-2.5 text-base leading-6 text-body">
          Checking which open opportunities fit the types and preferences you chose. Match scores and alerts follow as soon as matching launches.
        </p>

        <div className="mt-7 w-full max-w-[520px] rounded-field bg-night px-[18px] py-4 text-left font-mono text-xs leading-6" aria-live="polite">
          {lines.map((l, i) => (
            <p key={i} className={i === lines.length - 1 && !done ? "text-[#d9d2ea]" : "text-[#8b7fb0]"}>
              {l.at} → {l.text}
            </p>
          ))}
          {!done && !error && (
            <p className="flex items-center gap-2 text-[#d9d2ea]">
              {clock()} → <span className="size-[7px] animate-pulse rounded-full bg-signal" /> working…
            </p>
          )}
        </div>

        {error ? (
          <div className="mt-6 w-full max-w-[520px]">
            <Alert>We couldn&apos;t start your agent: {error}</Alert>
            <ButtonLink href="/dashboard" size="md" className="mt-4">
              Go to the dashboard
            </ButtonLink>
          </div>
        ) : (
          <p className="flex items-center gap-3 pt-6 text-sm text-body">
            <span className="size-5 animate-spin rounded-full border-2 border-brand-soft border-t-brand" aria-hidden />
            {done ? "Taking you to your Dashboard…" : "Starting…"}
          </p>
        )}
      </main>
    </div>
  );
}
