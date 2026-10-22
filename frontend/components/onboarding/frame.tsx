"use client";

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";

import { Logo } from "@/components/brand/logo";
import { Button, Spinner } from "@/components/ui/button";
import type { Me } from "@/lib/api/client";
import { STEPS } from "@/lib/onboarding/options";
import { useSaveStatus } from "@/lib/onboarding/save-status";
import { cn } from "@/lib/utils";

type Wizard = {
  me: Me;
  goTo: (step: number | "review") => void;
  /** The current step's flush(); "Save & exit" calls it. */
  registerFlush: (fn: () => Promise<boolean>) => void;
  saveAndExit: () => void;
};

export const WizardContext = createContext<Wizard | null>(null);
export function useWizard() {
  const ctx = useContext(WizardContext);
  if (!ctx) throw new Error("useWizard outside the onboarding wizard");
  return ctx;
}

export function SaveIndicator({ className }: { className?: string }) {
  const { state } = useSaveStatus();
  const text = {
    saved: "Saved automatically",
    pending: "Saving…",
    saving: "Saving…",
    error: "Couldn't save — check the fields",
    readonly: "Demo — changes aren't saved",
  }[state];
  const dot = { saved: "bg-success", pending: "bg-faint", saving: "bg-faint", error: "bg-danger", readonly: "bg-warning" }[state];
  return (
    <span role="status" className={cn("flex items-center gap-1.5 text-xs text-muted", className)}>
      <span className={cn("size-[7px] rounded-full", dot)} />
      {text}
    </span>
  );
}

export function WizardHeader({ exit = true }: { exit?: boolean }) {
  const wizard = useContext(WizardContext);
  return (
    <header className="flex h-[60px] items-center justify-between border-b border-line bg-surface px-4 md:h-[68px] md:px-10">
      <Logo href={null} />
      <div className="flex items-center gap-4">
        <SaveIndicator className="hidden sm:flex" />
        {exit && wizard && (
          <Button variant="ghost" size="sm" className="px-3 md:px-5" onClick={wizard.saveAndExit}>
            Save &amp; exit
          </Button>
        )}
      </div>
    </header>
  );
}

/**
 * Progress label + bar above the card. On the review screen it reflects the
 * real profile state: green "SETUP COMPLETE" only when nothing required is
 * missing; otherwise `step` is the number of fully filled steps.
 */
export function Progress({ step, review }: { step: number; review?: "complete" | "incomplete" }) {
  const complete = review === "complete";
  const title = complete
    ? "SETUP COMPLETE: Review your profile"
    : review === "incomplete"
      ? `REVIEW YOUR PROFILE · ${step} OF 5 STEPS DONE`
      : `STEP ${step} OF 5 · ${STEPS[step - 1].title}`;
  return (
    <div>
      <p className={cn("font-mono text-[13px] font-semibold uppercase", complete ? "text-success" : "text-brand")}>{title}</p>
      <div
        className="mt-2.5 h-2 overflow-hidden rounded bg-line"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={5}
        aria-valuenow={complete ? 5 : step}
        aria-label="Profile setup progress"
      >
        <div className={cn("h-full rounded transition-[width] duration-500", complete ? "bg-success" : "bg-brand")} style={{ width: `${(complete ? 5 : step) * 20}%` }} />
      </div>
    </div>
  );
}

type StepFrameProps = {
  step: number;
  /** Field errors; Continue is blocked while any is non-null. */
  errors: Record<string, string | null>;
  flush: () => Promise<boolean>;
  /** Runs after a successful save instead of moving to the next step (Finish setup). */
  onFinish?: () => Promise<void>;
  children: (showErrors: boolean) => ReactNode;
};

export function StepFrame({ step, errors, flush, onFinish, children }: StepFrameProps) {
  const { goTo, registerFlush } = useWizard();
  const { state } = useSaveStatus();
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const invalid = Object.values(errors).some(Boolean);

  useEffect(() => registerFlush(flush), [flush, registerFlush]);

  async function next() {
    setSubmitted(true);
    if (invalid) {
      // Let the error messages render, then bring the first one into view.
      requestAnimationFrame(() => root.current?.querySelector("[aria-invalid=true], .text-danger")?.scrollIntoView({ behavior: "smooth", block: "center" }));
      return;
    }
    setBusy(true);
    const ok = await flush();
    if (ok && onFinish) await onFinish();
    setBusy(false);
    if (ok && !onFinish) goTo(step + 1);
  }

  return (
    <div ref={root} className="rounded-card border border-line bg-surface px-5 py-7 shadow-[0_1px_1.5px_rgb(30_17_62/0.05)] sm:px-9 sm:py-8">
      {children(submitted)}
      <div className="mt-[26px] flex items-center justify-between gap-3 border-t border-line pt-[22px]">
        <Button variant="ghost" size="sm" className={cn("px-2 sm:px-5", step === 1 && "invisible")} onClick={() => goTo(step - 1)}>
          &lt; Back
        </Button>
        <div className="flex items-center gap-3.5">
          <SaveIndicator className="hidden sm:flex" />
          <Button size="sm" onClick={next} disabled={busy || state === "saving"}>
            {busy && <Spinner />}
            {step === 5 ? "Finish setup" : "Continue"}
          </Button>
        </div>
      </div>
    </div>
  );
}

/** Two-column row that stacks on phones. */
export function Row({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("grid gap-4 sm:grid-cols-2", className)}>{children}</div>;
}
