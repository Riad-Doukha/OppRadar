"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AuthTitle } from "@/components/auth/auth-card";
import { DemoLink } from "@/components/auth/demo-link";
import { Logo } from "@/components/brand/logo";
import { Alert } from "@/components/ui/alert";
import { Button, Spinner } from "@/components/ui/button";
import { Field, Input, PasswordInput } from "@/components/ui/field";
import { authError, type AuthError } from "@/lib/auth";
import { createClient } from "@/lib/supabase/client";
import { safeNext } from "@/lib/utils";

export function LoginForm() {
  const t = useTranslations("auth");
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<AuthError | "badLink" | null>(params.get("error") === "link" ? "badLink" : null);
  const [loading, setLoading] = useState(false);
  const credentialsError = error === "invalidCredentials";

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const { error } = await createClient().auth.signInWithPassword({ email: email.trim(), password });
    if (error) {
      setLoading(false);
      if (error.code === "email_not_confirmed") {
        router.push(`/check-email?email=${encodeURIComponent(email.trim())}`);
        return;
      }
      setError(authError(error));
      return;
    }
    router.push(safeNext(params.get("next")));
    router.refresh();
  }

  return (
    <>
      <Logo />
      <AuthTitle title={t("login.title")} subtitle={t("login.subtitle")} />

      {error && <Alert className="mt-6">{t(`errors.${error}`)}</Alert>}

      <form onSubmit={onSubmit} className="flex flex-col gap-4 pt-5" noValidate>
        <Field label={t("email")} error={credentialsError}>
          {(f) => (
            <Input
              {...f}
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("emailPlaceholder")}
            />
          )}
        </Field>
        <Field
          label={t("password")}
          error={credentialsError}
          aside={
            <Link href="/forgot-password" className="text-xs font-bold text-brand hover:text-brand-strong">
              {t("login.forgot")}
            </Link>
          }
        >
          {(f) => (
            <PasswordInput
              {...f}
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          )}
        </Field>
        <Button type="submit" block className="mt-2" disabled={loading || !email || !password}>
          {loading ? (
            <>
              <Spinner /> {t("login.loggingIn")}
            </>
          ) : (
            t("logIn")
          )}
        </Button>
      </form>

      <p className="pt-5 text-center text-sm text-muted">
        {t("login.newHere")}{" "}
        <Link href="/signup" className="font-bold text-brand hover:text-brand-strong">
          {t("login.create")}
        </Link>
      </p>
      <DemoLink />
    </>
  );
}
