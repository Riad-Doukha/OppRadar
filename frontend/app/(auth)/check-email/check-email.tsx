"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { AuthIcon, AuthTitle } from "@/components/auth/auth-card";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { RESEND_SECONDS, authError } from "@/lib/auth";
import { useCountdown } from "@/lib/hooks/use-countdown";
import { createClient } from "@/lib/supabase/client";

/** After sign-up: "We sent a verification link to …" with a throttled resend. */
export function CheckEmail() {
  const t = useTranslations("auth");
  const email = useSearchParams().get("email") ?? "";
  const timer = useCountdown(RESEND_SECONDS);
  const [status, setStatus] = useState<{ ok: boolean; text: string } | null>(null);

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
      <p className="pt-3.5 text-center">
        <Link href="/signup" className="text-sm font-bold text-brand hover:text-brand-strong">
          {t("wrongEmailBack")}
        </Link>
      </p>
    </>
  );
}
