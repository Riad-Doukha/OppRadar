"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AuthTitle } from "@/components/auth/auth-card";
import { DemoLink } from "@/components/auth/demo-link";
import { Logo } from "@/components/brand/logo";
import { Alert } from "@/components/ui/alert";
import { Button, Spinner } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, Input, PasswordInput } from "@/components/ui/field";
import { authErrorMessage, passwordProblem, passwordStrength } from "@/lib/auth";
import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";

export function SignupForm() {
  const router = useRouter();
  const [form, setForm] = useState({ fullName: "", email: "", password: "", confirm: "" });
  const [terms, setTerms] = useState(false);
  const [touched, setTouched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<"email" | "google" | null>(null);

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));

  const strength = passwordStrength(form.password);
  const problems = {
    fullName: form.fullName.trim().length < 2 ? "Enter your full name." : null,
    email: /^\S+@\S+\.\S+$/.test(form.email.trim()) ? null : "Enter a valid email.",
    password: passwordProblem(form.password),
    confirm: form.confirm && form.confirm === form.password ? null : "Passwords don't match.",
    terms: terms ? null : "Please accept the Terms and Privacy Policy.",
  };
  const valid = Object.values(problems).every((p) => p === null);
  const show = (key: keyof typeof problems) => (touched ? problems[key] ?? undefined : undefined);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!valid) return;
    setLoading("email");
    setError(null);
    const email = form.email.trim();
    const { data, error } = await createClient().auth.signUp({
      email,
      password: form.password,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback?next=/onboarding`,
        data: { full_name: form.fullName.trim(), terms_accepted: true },
      },
    });
    setLoading(null);
    if (error) return setError(authErrorMessage(error));
    // With e-mail confirmation on, Supabase hides existing accounts behind an
    // empty identities list instead of an error.
    if (data.user && data.user.identities?.length === 0)
      return setError("An account with this email already exists. Log in instead.");
    router.push(`/check-email?email=${encodeURIComponent(email)}`);
  }

  async function google() {
    if (!terms) {
      setTouched(true);
      return;
    }
    setLoading("google");
    const { error } = await createClient().auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback?next=/onboarding` },
    });
    if (error) {
      setLoading(null);
      setError(authErrorMessage(error));
    }
  }

  return (
    <>
      <Logo />
      <AuthTitle title="Create your account" subtitle="Free forever for students in Algeria. Takes about 2 minutes." />

      {error && <Alert className="mt-6">{error}</Alert>}

      <form onSubmit={onSubmit} className="flex flex-col gap-4 pt-6" noValidate>
        <Field label="Full name" error={show("fullName")}>
          {(f) => <Input {...f} autoComplete="name" value={form.fullName} onChange={set("fullName")} placeholder="Amine Benali" />}
        </Field>
        <Field label="Email" error={show("email")}>
          {(f) => <Input {...f} type="email" autoComplete="email" value={form.email} onChange={set("email")} placeholder="you@university.dz" />}
        </Field>
        <Field label="Password" error={show("password")}>
          {(f) => (
            <>
              <PasswordInput {...f} autoComplete="new-password" value={form.password} onChange={set("password")} />
              <div className="flex gap-1.5 pt-2" aria-hidden>
                {[1, 2, 3, 4].map((i) => (
                  <span key={i} className={cn("h-1 flex-1 rounded-sm", i <= strength.score ? "bg-brand" : "bg-line")} />
                ))}
              </div>
              {!show("password") && (
                <p className="pt-1.5 text-xs text-muted" aria-live="polite">
                  8+ characters with a number{strength.label && ` — strength: ${strength.label}`}
                </p>
              )}
            </>
          )}
        </Field>
        <Field label="Confirm password" error={show("confirm")}>
          {(f) => <PasswordInput {...f} autoComplete="new-password" value={form.confirm} onChange={set("confirm")} />}
        </Field>

        <div className="pt-1">
          <Checkbox checked={terms} onChange={(e) => setTerms(e.target.checked)}>
            I agree to the <strong className="text-ink">Terms</strong> and <strong className="text-ink">Privacy Policy</strong>
          </Checkbox>
          {show("terms") && <p className="pt-1.5 text-xs text-danger">{problems.terms}</p>}
        </div>

        <Button type="submit" block className="mt-1" disabled={loading !== null}>
          {loading === "email" ? (
            <>
              <Spinner /> Creating account…
            </>
          ) : (
            "Create account"
          )}
        </Button>
      </form>

      <div className="flex items-center gap-3 py-5 text-xs text-muted">
        <span className="h-px flex-1 bg-line" />
        or
        <span className="h-px flex-1 bg-line" />
      </div>

      <Button type="button" variant="neutral" size="md" block onClick={google} disabled={loading !== null}>
        {/* eslint-disable-next-line @next/next/no-img-element -- fixed-size brand mark */}
        <img src="/icons/google.svg" alt="" width={18} height={18} />
        Continue with Google
      </Button>

      <p className="pt-5 text-center text-sm text-muted">
        Already have an account?{" "}
        <Link href="/login" className="font-bold text-brand hover:text-brand-strong">
          Log in
        </Link>
      </p>
      <DemoLink />
    </>
  );
}
