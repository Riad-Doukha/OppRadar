"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AuthIcon, AuthTitle } from "@/components/auth/auth-card";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { RESEND_SECONDS, authError } from "@/lib/auth";
import { useCountdown } from "@/lib/hooks/use-countdown";
import { forgetSignup, pendingSignup } from "@/lib/pending-signup";
import { createClient } from "@/lib/supabase/client";

// Supabase limits sign-in attempts per IP (about 30 per 5 minutes): one try
// every 15 s, plus one each time the tab comes back into view.
const POLL_MS = 15_000;
const GIVE_UP_MS = 30 * 60_000;

/**
 * After sign-up: "We sent a verification link to …" with a throttled resend.
 * The link may be opened on another device (phone), which signs in only that
 * device; so while this tab still has the sign-up in memory, it signs itself
 * in as soon as the account is confirmed and continues to the setup.
 */
export function CheckEmail() {
  const t = useTranslations("auth");
  const router = useRouter();
  const email = useSearchParams().get("email") ?? "";
  const timer = useCountdown(RESEND_SECONDS);
  const [status, setStatus] = useState<{ ok: boolean; text: string } | null>(null);
  const [waiting, setWaiting] = useState(false);

  useEffect(() => {
    const creds = pendingSignup(email);
    if (!creds) return;
    setWaiting(true);
    const started = Date.now();
    let busy = false;
    let done = false;
    async function attempt() {
      if (busy || done) return;
      if (Date.now() - started > GIVE_UP_MS) return stop();
      busy = true;
      const { error } = await createClient().auth.signInWithPassword(creds!);
      busy = false;
      if (error) {
        // Still unconfirmed: keep waiting. Anything else (rate limit, password
        // changed…): stop and leave the "Log in here" link.
        if (error.code !== "email_not_confirmed") stop();
        return;
      }
      stop();
      forgetSignup();
      router.push("/onboarding");
      router.refresh();
    }
    function stop() {
      done = true;
      setWaiting(false);
      clearInterval(timerId);
      document.removeEventListener("visibilitychange", onVisible);
    }
    const onVisible = () => document.visibilityState === "visible" && attempt();
    const timerId = setInterval(attempt, POLL_MS);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      done = true;
      clearInterval(timerId);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [email, router]);

  async function resend() {
    setStatus(null);
    const { error } = await createClient().auth.resend({
      type: "signup",
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback?next=/onboarding` },
    });
    timer.restart();
    setStatus(error ? { ok: false, text: t(`errors.${authError(error)}`) } : { ok: true, text: t("check.sentAgain") });
  }

  return (
    <>
      <AuthIcon src="/icons/mail-purple.svg" tone="brand" />
      <AuthTitle center title={t("check.title")} />
      <p className="pt-2 text-center text-[15px] leading-6 text-body">
        {t("check.sentTo")}
        <br />
        <span className="font-mono font-bold break-all text-ink">{email || t("check.yourEmail")}</span>
      </p>
      <p className="pt-2 text-center text-xs text-muted">{t("check.clickLink")}</p>
      {waiting && (
        <p role="status" className="pt-1 text-center text-xs text-muted">
          {t("check.waiting")}
        </p>
      )}

      <Alert tone="info" className="mt-[22px] mb-[18px] text-[13px]">
        {t("check.nothingYet")}
        {!timer.done && (
          <>
            {" "}— <span className="font-mono font-bold text-ink">{timer.label}</span>
          </>
        )}
      </Alert>

      {status && (
        <p role="status" className={`pb-3 text-center text-xs ${status.ok ? "text-success" : "text-danger"}`}>
          {status.text}
        </p>
      )}

      <Button variant="outline" size="md" block onClick={resend} disabled={!timer.done || !email}>
        {t("check.resendEmail")}
      </Button>
      <p className="pt-4 text-center text-sm text-muted">
        {t("check.otherDevice")}{" "}
        <Link href={`/login${email ? `?email=${encodeURIComponent(email)}` : ""}`} className="font-bold text-brand hover:text-brand-strong">
          {t("check.logIn")}
        </Link>
      </p>
      <p className="pt-2 text-center">
        <Link href="/signup" className="text-sm font-bold text-brand hover:text-brand-strong">
          {t("wrongEmailBack")}
        </Link>
      </p>
    </>
  );
}
