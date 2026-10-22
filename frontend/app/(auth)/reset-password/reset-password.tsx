"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AuthTitle } from "@/components/auth/auth-card";
import { Logo } from "@/components/brand/logo";
import { Alert } from "@/components/ui/alert";
import { Button, Spinner } from "@/components/ui/button";
import { Field, PasswordInput } from "@/components/ui/field";
import { authError, passwordProblem, type AuthError } from "@/lib/auth";
import { createClient } from "@/lib/supabase/client";

export function ResetPassword() {
  const t = useTranslations("auth");
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [touched, setTouched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<AuthError | "resetExpired" | null>(null);

  const rule = passwordProblem(password);
  const problem = rule && t(`rules.${rule}`);
  const mismatch = confirm !== password ? t("rules.mismatch") : null;

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
        error.code === "session_not_found" || error.status === 401 ? "resetExpired" : authError(error),
      );
      return;
    }
    router.push("/onboarding");
    router.refresh();
  }

  return (
    <>
      <Logo />
      <AuthTitle title={t("reset.title")} subtitle={t("rules.hint")} />
      {error && (
        <Alert className="mt-6">
          {t(`errors.${error}`)}{" "}
          {error === "resetExpired" && (
            <Link href="/forgot-password" className="font-bold underline">
              {t("reset.sendNew")}
            </Link>
          )}
        </Alert>
      )}
      <form onSubmit={onSubmit} className="flex flex-col gap-4 pt-6" noValidate>
        <Field label={t("newPassword")} error={touched ? problem ?? undefined : undefined}>
          {(f) => <PasswordInput {...f} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <Field label={t("confirmPassword")} error={touched ? mismatch ?? undefined : undefined}>
          {(f) => <PasswordInput {...f} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />}
        </Field>
        <Button type="submit" block className="mt-2" disabled={loading}>
          {loading ? (
            <>
              <Spinner /> {t("reset.saving")}
            </>
          ) : (
            t("reset.save")
          )}
        </Button>
      </form>
    </>
  );
}
