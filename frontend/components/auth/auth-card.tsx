import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Centered white card on the lavender glow, shared by every auth screen. */
export function AuthCard({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <main className="auth-backdrop flex min-h-dvh items-center justify-center px-4 py-12 sm:px-6">
      <div className={cn("w-full max-w-[460px] rounded-card border border-line bg-surface p-6 shadow-card sm:p-9", className)}>
        {children}
      </div>
    </main>
  );
}

export function AuthTitle({ title, subtitle, center }: { title: string; subtitle?: ReactNode; center?: boolean }) {
  return (
    <div className={cn(center && "text-center")}>
      <h1 className="pt-[18px] font-display text-[26px] font-bold text-ink">{title}</h1>
      {subtitle && <p className="pt-1.5 text-sm text-muted">{subtitle}</p>}
    </div>
  );
}

/** Round tinted badge with an icon, used on the "check your email" screens. */
export function AuthIcon({ src, tone }: { src: string; tone: "brand" | "success" }) {
  return (
    <div className="flex justify-center pt-1">
      <div className={cn("flex items-center justify-center", tone === "brand" ? "size-[72px] rounded-3xl bg-brand-soft" : "size-16 rounded-full bg-success-tint")}>
        {/* eslint-disable-next-line @next/next/no-img-element -- fixed-size decorative SVG */}
        <img src={src} alt="" width={tone === "brand" ? 34 : 30} height={tone === "brand" ? 34 : 30} />
      </div>
    </div>
  );
}
