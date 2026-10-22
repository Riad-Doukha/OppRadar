"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AuthTitle } from "@/components/auth/auth-card";
import { DemoLink } from "@/components/auth/demo-link";
import { Logo } from "@/components/brand/logo";
import { Alert } from "@/components/ui/alert";
import { Button, Spinner } from "@/components/ui/button";
import { Field, Input, PasswordInput } from "@/components/ui/field";
import { authErrorMessage } from "@/lib/auth";
import { createClient } from "@/lib/supabase/client";
import { safeNext } from "@/lib/utils";

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(
    params.get("error") === "link" ? "That link is invalid or has expired. Log in or request a new one." : null,
  );
  const [loading, setLoading] = useState(false);
  const credentialsError = error?.startsWith("Wrong email");

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
      setError(authErrorMessage(error));
      return;
    }
    router.push(safeNext(params.get("next")));
    router.refresh();
  }

  return (
    <>
      <Logo />
      <AuthTitle title="Welcome back" subtitle="Log in to see what your agent found." />

      {error && <Alert className="mt-6">{error}</Alert>}

      <form onSubmit={onSubmit} className="flex flex-col gap-4 pt-5" noValidate>
        <Field label="Email" error={credentialsError}>
          {(f) => (
            <Input
              {...f}
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@university.dz"
            />
          )}
        </Field>
        <Field
          label="Password"
          error={credentialsError}
          aside={
            <Link href="/forgot-password" className="text-xs font-bold text-brand hover:text-brand-strong">
              Forgot password?
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
              <Spinner /> Logging in…
            </>
          ) : (
            "Log in"
          )}
        </Button>
      </form>

      <p className="pt-5 text-center text-sm text-muted">
        New here?{" "}
        <Link href="/signup" className="font-bold text-brand hover:text-brand-strong">
          Create an account
        </Link>
      </p>
      <DemoLink />
    </>
  );
}
