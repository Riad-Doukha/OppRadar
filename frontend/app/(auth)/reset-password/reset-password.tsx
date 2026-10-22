"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AuthTitle } from "@/components/auth/auth-card";
import { Logo } from "@/components/brand/logo";
import { Alert } from "@/components/ui/alert";
import { Button, Spinner } from "@/components/ui/button";
import { Field, PasswordInput } from "@/components/ui/field";
import { authErrorMessage, passwordProblem } from "@/lib/auth";
import { createClient } from "@/lib/supabase/client";

export function ResetPassword() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [touched, setTouched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const problem = passwordProblem(password);
  const mismatch = confirm !== password ? "Passwords don't match." : null;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (problem || mismatch) return;
    setLoading(true);
    setError(null);
    const { error } = await createClient().auth.updateUser({ password });
    setLoading(false);
    if (error) {
      setError(
        error.code === "session_not_found" || error.status === 401
          ? "This reset link has expired. Request a new one."
          : authErrorMessage(error),
      );
      return;
    }
    router.push("/onboarding");
    router.refresh();
  }

  return (
    <>
      <Logo />
      <AuthTitle title="Choose a new password" subtitle="8+ characters with a number." />
      {error && (
        <Alert className="mt-6">
          {error}{" "}
          {error.includes("expired") && (
            <Link href="/forgot-password" className="font-bold underline">
              Send a new link
            </Link>
          )}
        </Alert>
      )}
      <form onSubmit={onSubmit} className="flex flex-col gap-4 pt-6" noValidate>
        <Field label="New password" error={touched ? problem ?? undefined : undefined}>
          {(f) => <PasswordInput {...f} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <Field label="Confirm password" error={touched ? mismatch ?? undefined : undefined}>
          {(f) => <PasswordInput {...f} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />}
        </Field>
        <Button type="submit" block className="mt-2" disabled={loading}>
          {loading ? (
            <>
              <Spinner /> Saving…
            </>
          ) : (
            "Save password"
          )}
        </Button>
      </form>
    </>
  );
}
