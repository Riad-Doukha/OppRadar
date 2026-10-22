import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Grey placeholder block; pulses unless the user prefers reduced motion. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("rounded-md bg-line/70 motion-safe:animate-pulse", className)} />;
}

/** Wraps a skeleton layout so screen readers hear "Loading…" once instead of empty boxes. */
export function Loading({ label = "Loading…", children, className }: { label?: string; children: ReactNode; className?: string }) {
  return (
    <div role="status" aria-busy className={className}>
      <span className="sr-only">{label}</span>
      {children}
    </div>
  );
}

/** Placeholder shaped like an opportunity card (dashboard feed). */
export function OpportunityCardSkeleton() {
  return (
    <div className="rounded-card border border-line bg-surface p-[22px]">
      <div className="flex gap-2">
        <Skeleton className="h-7 w-24 rounded-full" />
        <Skeleton className="h-7 w-16 rounded-full" />
      </div>
      <Skeleton className="mt-3.5 h-5 w-2/3" />
      <Skeleton className="mt-2.5 h-3.5 w-1/2" />
      <Skeleton className="mt-3 h-3.5 w-11/12" />
      <Skeleton className="mt-3.5 h-4 w-48" />
      <div className="mt-4 flex items-center justify-between border-t border-line pt-4">
        <Skeleton className="h-3.5 w-32" />
        <div className="flex gap-2.5">
          <Skeleton className="h-10 w-20 rounded-field" />
          <Skeleton className="h-10 w-28 rounded-field" />
        </div>
      </div>
    </div>
  );
}

/** Placeholder for a labelled input (onboarding steps). */
export function FieldSkeleton({ className }: { className?: string }) {
  return (
    <div className={className}>
      <Skeleton className="h-3.5 w-24" />
      <Skeleton className="mt-2 h-11 w-full rounded-field" />
    </div>
  );
}
