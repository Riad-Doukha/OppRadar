"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import { AuthIcon, AuthTitle } from "@/components/auth/auth-card";
import { Alert } from "@/components/ui/alert";
import { Button, Spinner } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { RESEND_SECONDS, RESET_LINK_MINUTES, authError, type AuthError } from "@/lib/auth";
import { useCountdown } from "@/lib/hooks/use-countdown";
import { createClient } from "@/lib/supabase/client";

export function ForgotPassword() {
  const t = useTranslations("auth");
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<AuthError | null>(null);
  const timer = useCountdown(0);

  async function send(e?: FormEvent) {
    e?.preventDefault();
    setLoading(true);
    setError(null);
    const { error } = await createClient().auth.resetPasswordForEmail(email.trim(), {
      redirectTo: `${window.location.origin}/auth/callback?next=/reset-password`,
    });
    setLoading(false);
    // Same screen whether or not the account exists, so emails can't be probed.
    if (error && error.status !== 400) return setError(authError(error));
    setSent(true);
    timer.restart(RESEND_SECONDS);
  }

  if (sent) {
    return (
      <>
        <AuthIcon src="/icons/check-green.svg" tone="success" />
        <AuthTitle center title={t("forgot.inboxTitle")} />
        <p className="pt-2 text-center text-[15px] leading-6 text-body">
          {t("forgot.sentTo")}
          <br />
          <span className="font-mono font-bold break-all text-ink">{email.trim()}</span>
        </p>
        <p className="pt-1.5 pb-[22px] text-center text-xs text-muted">{t("forgot.expires", { minutes: RESET_LINK_MINUTES })}</p>
        {error && <Alert className="mb-4">{t(`errors.${error}`)}</Alert>}
        <Button size="lg" block onClick={() => (window.location.href = "mailto:")}>
          {t("forgot.openMail")}
        </Button>
        <p className="pt-5 text-center text-sm text-muted">
          {t("forgot.didntGet")}{" "}
          <button type="button" onClick={() => send()} disabled={!timer.done || loading} className="font-bold text-brand enabled:hover:text-brand-strong disabled:opacity-70">
            {timer.done ? t("resend") : t("resendIn", { time: timer.label })}
          </button>
        </p>
        <p className="pt-2 text-center">
          <button type="button" onClick={() => setSent(false)} className="text-sm font-bold text-brand hover:text-brand-strong">
            {t("wrongEmailBack")}
          </button>
        </p>
      </>
    );
  }

  return (
    <>
      <Link href="/login" className="text-sm text-muted hover:text-ink">
        <span className="inline-block rtl:-scale-x-100">&lt;</span> {t("forgot.backToLogin")}
      </Link>
      <h1 className="pt-4 font-display text-[26px] font-bold text-ink">{t("forgot.title")}</h1>
      <p className="pt-1.5 text-sm text-muted">{t("forgot.subtitle")}</p>

      {error && <Alert className="mt-5">{t(`errors.${error}`)}</Alert>}

      <form onSubmit={send} className="flex flex-col gap-6 pt-5" noValidate>
        <Field label={t("email")} hint={t("forgot.emailHint")}>
          {(f) => <Input {...f} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder={t("emailPlaceholder")} />}
        </Field>
        <Button type="submit" block disabled={loading || !/^\S+@\S+\.\S+$/.test(email.trim())}>
          {loading ? (
            <>
              <Spinner /> {t("forgot.sending")}
            </>
          ) : (
            t("forgot.send")
          )}
        </Button>
      </form>

      <p className="pt-5 text-center text-sm text-muted">
        {t("forgot.remembered")}{" "}
        <Link href="/login" className="font-bold text-brand hover:text-brand-strong">
          {t("logIn")}
        </Link>
      </p>
    </>
  );
}
