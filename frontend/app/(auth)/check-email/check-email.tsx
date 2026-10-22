"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";

import { AuthIcon, AuthTitle } from "@/components/auth/auth-card";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { RESEND_SECONDS, authErrorMessage } from "@/lib/auth";
import { useCountdown } from "@/lib/hooks/use-countdown";
import { createClient } from "@/lib/supabase/client";

/** After sign-up: "We sent a verification link to …" with a throttled resend. */
export function CheckEmail() {
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
    setStatus(error ? { ok: false, text: authErrorMessage(error) } : { ok: true, text: "Sent again. Check your inbox." });
  }

  return (
    <>
      <AuthIcon src="/icons/mail-purple.svg" tone="brand" />
      <AuthTitle center title="Check your email" />
      <p className="pt-2 text-center text-[15px] leading-6 text-body">
        We sent a verification link to
        <br />
        <span className="font-mono font-bold break-all text-ink">{email || "your email"}</span>
      </p>
      <p className="pt-2 text-center text-xs text-muted">Click the link to continue to your profile setup.</p>

      <Alert tone="info" className="mt-[22px] mb-[18px] text-[13px]">
        Nothing yet? Check spam, or resend
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
        Resend email
      </Button>
      <p className="pt-3.5 text-center">
        <Link href="/signup" className="text-sm font-bold text-brand hover:text-brand-strong">
          Wrong email? Go back
        </Link>
      </p>
    </>
  );
}
