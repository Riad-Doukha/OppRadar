"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { AuthCard } from "@/components/auth/auth-card";
import { Logo } from "@/components/brand/logo";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { api, type Me } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";

/**
 * Temporary landing spot after log-in until the onboarding wizard and the
 * dashboard are built. Proves the session reaches the backend (`GET /me`).
 */
export function SignedInPlaceholder({ title }: { title: string }) {
  const router = useRouter();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });

  async function logOut() {
    await createClient().auth.signOut();
    router.push("/");
    router.refresh();
  }

  return (
    <AuthCard>
      <Logo />
      <h1 className="pt-[18px] font-display text-[26px] font-bold text-ink">{title}</h1>
      {me.isPending && <p className="pt-2 text-sm text-muted">Loading your profile…</p>}
      {me.isError && <Alert className="mt-4">We couldn&apos;t load your profile: {me.error.message}</Alert>}
      {me.data && (
        <p className="pt-2 text-sm text-body">
          Signed in as <strong className="text-ink">{me.data.full_name ?? me.data.email}</strong>
          {me.data.is_demo && " (read-only demo)"} · onboarding step {me.data.onboarding.step} of 5
          {me.data.onboarding.completed_at && " · completed"}.
        </p>
      )}
      <p className="pt-4 text-sm text-muted">This screen is a placeholder — the real one is being built next.</p>
      <Button variant="outline" size="md" block className="mt-6" onClick={logOut}>
        Log out
      </Button>
    </AuthCard>
  );
}
