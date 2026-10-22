"use client";

import type { ReactNode } from "react";

import { SectionLabel } from "@/components/ui/inputs";
import { cn } from "@/lib/utils";

/** White settings card with a mono section label ("ACCOUNT", "DANGER ZONE"…). */
export function SettingsCard({ label, danger, children, className }: { label: ReactNode; danger?: boolean; children: ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-card border bg-surface px-5 py-6 shadow-[0_1px_1.5px_rgb(30_17_62/0.05)] sm:px-7", danger ? "border-danger-line" : "border-line", className)}>
      <SectionLabel className={danger ? "text-danger" : undefined}>{label}</SectionLabel>
      <div className="pt-2.5">{children}</div>
    </section>
  );
}

/** Title + description on the left, a control on the right; stacks on phones. */
export function SettingRow({ title, description, children, boxed, last, id }: { title: ReactNode; description?: ReactNode; children?: ReactNode; boxed?: boolean; last?: boolean; id?: string }) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-[18px]",
        boxed ? "mb-2.5 rounded-field border border-line bg-page/60 px-4 py-3.5" : cn("py-4", !last && "border-b border-line"),
      )}
    >
      <div className="min-w-0 flex-1">
        <p id={id} className={cn("text-ink", boxed ? "text-[15px]" : "text-[15px] font-bold")}>
          {title}
        </p>
        {description && <div className="pt-[3px] text-[13.5px] leading-[20.25px] text-muted">{description}</div>}
      </div>
      {children && <div className="flex shrink-0 flex-wrap items-center gap-2.5">{children}</div>}
    </div>
  );
}

/** Purple switch from the design (50×28). */
export function Toggle({ checked, onChange, disabled, label }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative h-7 w-[50px] shrink-0 rounded-2xl transition-colors focus-visible:shadow-focus disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "bg-brand" : "bg-line",
      )}
    >
      <span className={cn("absolute top-[3px] size-[22px] rounded-full bg-white shadow-[0_1px_4px_rgb(0_0_0/0.2)] transition-[left]", checked ? "left-[25px]" : "left-[3px]")} />
    </button>
  );
}

/** Grey "Soon" / "never allowed" chip. */
export function Badge({ children, tone = "muted" }: { children: ReactNode; tone?: "muted" | "success" | "warning" }) {
  const tones = { muted: "bg-line text-muted", success: "bg-[#ecfdf5] text-success", warning: "bg-[#fffbeb] text-warning" };
  return <span className={cn("flex h-7 items-center rounded-full px-3 text-[13px] font-bold whitespace-nowrap", tones[tone])}>{children}</span>;
}

/**
 * Two-option picker where only some options work yet (e.g. English | العربية soon).
 * Unavailable options are visible but disabled with a "soon" hint.
 */
export function Choice<T extends string>({
  value,
  options,
  onChange,
  label,
  disabled,
}: {
  value: T;
  options: { value: T; label: ReactNode; soon?: boolean }[];
  onChange?: (v: T) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="flex gap-[3px] rounded-[10px] bg-page p-[3px]">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={disabled || o.soon}
            title={o.soon ? "Coming soon" : undefined}
            onClick={() => onChange?.(o.value)}
            className={cn(
              "rounded-lg px-3.5 py-[7px] text-[13px] disabled:cursor-not-allowed",
              active ? "bg-surface font-bold text-ink shadow-[0_1px_1.5px_rgb(30_17_62/0.1)]" : "font-medium text-muted enabled:hover:text-ink",
              o.soon && "opacity-60",
            )}
          >
            {o.label}
            {o.soon && <span className="ml-1 font-mono text-[10px]">soon</span>}
          </button>
        );
      })}
    </div>
  );
}

/** Small inline status under a card ("Saved", errors). */
export function Status({ text, error }: { text: string | null; error?: boolean }) {
  if (!text) return null;
  return (
    <p role={error ? "alert" : "status"} className={cn("pt-2 text-xs", error ? "text-danger" : "text-success")}>
      {text}
    </p>
  );
}
