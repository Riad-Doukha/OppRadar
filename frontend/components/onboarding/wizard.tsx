"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useRef, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/button";
import { api, type Me } from "@/lib/api/client";
import { filled } from "@/lib/onboarding/body";
import { SaveStatusProvider } from "@/lib/onboarding/save-status";
import { createClient } from "@/lib/supabase/client";

import type { Prefill } from "./cv-upload";
import { Progress, WizardContext, WizardHeader } from "./frame";
import { Review } from "./review";
import { StepAbout } from "./step-about";
import { StepAlerts } from "./step-alerts";
import { StepEducation } from "./step-education";
import { StepGoals } from "./step-goals";
import { StepSkills } from "./step-skills";

/**
 * The 5-step profile setup. The step lives in the URL (?step=1..5|review) so
 * refresh and browser back work; every step autosaves to PATCH /me/onboarding/*.
 */
export function OnboardingWizard() {
  const router = useRouter();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  const flushRef = useRef<() => Promise<boolean>>(async () => true);
  // Bumped after the CV prefill is applied so step forms re-read the profile.
  const [formKey, setFormKey] = useState(0);

  const requested = params.get("step");
  const step: number | "review" = useMemo(() => {
    if (requested === "review") return "review";
    const n = Number(requested);
    if (n >= 1 && n <= 5) return n;
    if (!me.data) return 1;
    return me.data.onboarding.completed_at ? "review" : Math.min(Math.max(me.data.onboarding.step, 1), 5);
  }, [requested, me.data]);

  const goTo = useCallback(
    (to: number | "review") => {
      if (to === 0) return;
      router.push(`/onboarding?step=${to}`);
      window.scrollTo({ top: 0 });
    },
    [router],
  );
  const registerFlush = useCallback((fn: () => Promise<boolean>) => {
    flushRef.current = fn;
  }, []);
  const saveAndExit = useCallback(async () => {
    await flushRef.current();
    router.push("/dashboard");
  }, [router]);
  // Sign-up redirects signed-in users away, so leave the demo session first.
  const leaveDemo = useCallback(async () => {
    await createClient().auth.signOut();
    queryClient.clear();
    router.push("/signup");
    router.refresh();
  }, [queryClient, router]);

  /** "Use these details": write the CV values that were found, without wiping what the user typed. */
  const applyPrefill = useCallback(
    async (p: Prefill) => {
      const patch = (path: string, body: object) => (Object.keys(body).length ? api<Me>(path, { method: "PATCH", body: JSON.stringify(body) }) : null);
      const current = queryClient.getQueryData<Me>(["me"]);
      const skills = [...(current?.skills ?? []).map(({ name, level }) => ({ name, level })), ...(p.skills?.skills ?? [])];
      const languages = [...(current?.languages ?? []).map(({ language, level }) => ({ language, level })), ...(p.about?.languages ?? [])];
      const links = [...(current?.links ?? []).map(({ kind, url }) => ({ kind, url })), ...(p.goals?.links ?? [])];
      await patch("/me/onboarding/about", filled({ ...p.about, languages: dedupe(languages, "language") }));
      await patch("/me/onboarding/education", filled(p.education ?? {}));
      await patch("/me/onboarding/skills", filled({ skills: dedupe(skills, "name") }));
      await patch("/me/onboarding/goals", filled({ links: dedupe(links, "url") }));
      for (const x of p.experiences ?? []) await api("/me/experiences", { method: "POST", body: JSON.stringify(x) });
      for (const c of p.certificates ?? []) await api("/me/certificates", { method: "POST", body: JSON.stringify(c) });
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      setFormKey((k) => k + 1);
    },
    [queryClient],
  );

  if (me.isPending) {
    return (
      <Shell>
        <p className="flex items-center gap-2 py-20 text-sm text-muted">
          <Spinner className="text-brand" /> Loading your profile…
        </p>
      </Shell>
    );
  }
  if (me.isError) {
    return (
      <Shell>
        <Alert className="mt-10">We couldn&apos;t load your profile: {me.error.message}. Is the API running?</Alert>
      </Shell>
    );
  }

  return (
    <WizardContext.Provider value={{ me: me.data, goTo, registerFlush, saveAndExit }}>
      <SaveStatusProvider readOnly={me.data.is_demo}>
        <Shell wide={step === "review"} exit={step !== "review"}>
          {me.data.is_demo && (
            <Alert tone="info" className="mb-5">
              You&apos;re exploring the read-only demo profile, so nothing is saved and CV upload is off.{" "}
              <button type="button" onClick={leaveDemo} className="font-bold text-brand underline hover:text-brand-strong">
                Create your account
              </button>
            </Alert>
          )}
          <Progress step={step === "review" ? 5 : step} complete={step === "review"} />
          <div className="pt-7" key={`${step}-${formKey}`}>
            {step === 1 && <StepAbout onApplyPrefill={applyPrefill} />}
            {step === 2 && <StepEducation />}
            {step === 3 && <StepSkills />}
            {step === 4 && <StepGoals />}
            {step === 5 && <StepAlerts />}
            {step === "review" && <Review />}
          </div>
        </Shell>
      </SaveStatusProvider>
    </WizardContext.Provider>
  );
}

function Shell({ children, wide, exit = true }: { children: React.ReactNode; wide?: boolean; exit?: boolean }) {
  return (
    <div className="min-h-dvh bg-page">
      <WizardHeader exit={exit} />
      <main className={`mx-auto px-4 pt-9 pb-16 sm:px-8 ${wide ? "max-w-[820px]" : "max-w-[760px]"}`}>{children}</main>
    </div>
  );
}

function dedupe<T extends Record<K, string>, K extends string>(rows: T[], key: K): T[] {
  const seen = new Set<string>();
  return rows.filter((r) => {
    const k = r[key].toLowerCase();
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}
