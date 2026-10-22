"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { AuthIcon, AuthTitle } from "@/components/auth/auth-card";
import { Alert } from "@/components/ui/alert";
import { Button, Spinner } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { RESEND_SECONDS, RESET_LINK_MINUTES, authErrorMessage } from "@/lib/auth";
import { useCountdown } from "@/lib/hooks/use-countdown";
import { createClient } from "@/lib/supabase/client";

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
    if (error && error.status !== 400) return setError(authErrorMessage(error));
    setSent(true);
    timer.restart(RESEND_SECONDS);
  }

  if (sent) {
    return (
      <>
        <AuthIcon src="/icons/check-green.svg" tone="success" />
        <AuthTitle center title="Check your inbox" />
        <p className="pt-2 text-center text-[15px] leading-6 text-body">
          We sent a reset link to
          <br />
          <span className="font-mono font-bold break-all text-ink">{email.trim()}</span>
        </p>
        <p className="pt-1.5 pb-[22px] text-center text-xs text-muted">The link expires in {RESET_LINK_MINUTES} minutes.</p>
        {error && <Alert className="mb-4">{error}</Alert>}
        <Button size="lg" block onClick={() => (window.location.href = "mailto:")}>
          Open my email app
        </Button>
        <p className="pt-5 text-center text-sm text-muted">
          Didn&apos;t get it?{" "}
          <button type="button" onClick={() => send()} disabled={!timer.done || loading} className="font-bold text-brand enabled:hover:text-brand-strong disabled:opacity-70">
            {timer.done ? "Resend" : `Resend in ${timer.label}`}
          </button>
        </p>
        <p className="pt-2 text-center">
          <button type="button" onClick={() => setSent(false)} className="text-sm font-bold text-brand hover:text-brand-strong">
            Wrong email? Go back
          </button>
        </p>
      </>
    );
  }

  return (
    <>
      <Link href="/login" className="text-sm text-muted hover:text-ink">
        &lt; Back to log in
      </Link>
      <h1 className="pt-4 font-display text-[26px] font-bold text-ink">Reset your password</h1>
      <p className="pt-1.5 text-sm text-muted">Enter the email you signed up with. We&apos;ll send a reset link.</p>

      {error && <Alert className="mt-5">{error}</Alert>}

      <form onSubmit={send} className="flex flex-col gap-6 pt-5" noValidate>
        <Field label="Email" hint="Only you can see this. We never email you without consent.">
          {(f) => <Input {...f} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@university.dz" />}
        </Field>
        <Button type="submit" block disabled={loading || !/^\S+@\S+\.\S+$/.test(email.trim())}>
          {loading ? (
            <>
              <Spinner /> Sending…
            </>
          ) : (
            "Send reset link"
          )}
        </Button>
      </form>

      <p className="pt-5 text-center text-sm text-muted">
        Remembered it?{" "}
        <Link href="/login" className="font-bold text-brand hover:text-brand-strong">
          Log in
        </Link>
      </p>
    </>
  );
}
