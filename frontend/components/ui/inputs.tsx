"use client";

import { useTranslations } from "next-intl";
import { useState, type ComponentProps, type KeyboardEvent, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Native select styled like the design's fields (keeps keyboard + mobile pickers). */
export function Select({ className, invalid, describedBy, children, ...props }: ComponentProps<"select"> & { invalid?: boolean; describedBy?: string }) {
  return (
    <select
      aria-invalid={invalid || undefined}
      aria-describedby={describedBy}
      className={cn(
        "h-11 w-full appearance-none rounded-field border bg-surface select-chevron pe-9 ps-3.5 text-[15px] text-ink outline-none focus:border-brand focus:shadow-focus",
        invalid ? "border-danger" : "border-line",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}

/** Lavender pill used for skills, languages, interests and experience kinds. */
export function Pill({ children, onRemove, className, muted }: { children: ReactNode; onRemove?: () => void; className?: string; muted?: boolean }) {
  const t = useTranslations("common");
  return (
    <span
      className={cn(
        "inline-flex h-7 shrink-0 items-center gap-1.5 rounded-full px-3.5 text-[13px]",
        muted ? "border border-line bg-surface font-medium text-body" : "bg-brand-soft font-bold text-brand-strong",
        className,
      )}
    >
      {children}
      {onRemove && (
        <button type="button" onClick={onRemove} className="opacity-60 hover:opacity-100" aria-label={t("removeItem", { item: typeof children === "string" ? children : "" })}>
          ×
        </button>
      )}
    </span>
  );
}

/** Basic / Good / Fluent style picker (radio group). */
export function Segmented<T extends string>({ value, options, onChange, label }: { value: T | null | undefined; options: readonly { value: T; label: string }[]; onChange: (v: T) => void; label: string }) {
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
            onClick={() => onChange(o.value)}
            className={cn("rounded-lg px-3 py-[7px] text-[13px] sm:px-3.5", active ? "bg-surface font-bold text-ink shadow-[0_1px_1.5px_rgb(30_17_62/0.1)]" : "font-medium text-muted hover:text-ink")}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/** Field with removable pills and a free-text input; Enter or comma adds. */
export function TagInput({ values, onChange, placeholder, suggestions = [], max = 40, invalid, id }: { values: string[]; onChange: (v: string[]) => void; placeholder: string; suggestions?: string[]; max?: number; invalid?: boolean; id?: string }) {
  const t = useTranslations("common");
  const [draft, setDraft] = useState("");
  const has = (v: string) => values.some((x) => x.toLowerCase() === v.toLowerCase());
  const add = (raw: string) => {
    const v = raw.trim().replace(/,$/, "").trim();
    if (v && !has(v) && values.length < max) onChange([...values, v.slice(0, 60)]);
    setDraft("");
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add(draft);
    } else if (e.key === "Backspace" && !draft && values.length) {
      onChange(values.slice(0, -1));
    }
  };
  const open = suggestions.filter((s) => !has(s));
  return (
    <div>
      <div className={cn("flex min-h-12 flex-wrap items-center gap-2 rounded-field border bg-surface px-3 py-2 focus-within:border-brand focus-within:shadow-focus", invalid ? "border-danger" : "border-line")}>
        {values.map((v) => (
          <Pill key={v} onRemove={() => onChange(values.filter((x) => x !== v))}>
            {v}
          </Pill>
        ))}
        <input
          id={id}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKey}
          onBlur={() => draft && add(draft)}
          placeholder={placeholder}
          className="min-w-[120px] flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-faint"
        />
      </div>
      {open.length > 0 && (
        <p className="pt-1.5 text-xs text-muted">
          {t("suggestions")}{" "}
          {open.map((s, i) => (
            <span key={s}>
              {i > 0 && " · "}
              <button type="button" onClick={() => add(s)} className="hover:text-brand">
                {s}
              </button>
            </span>
          ))}
        </p>
      )}
    </div>
  );
}

/** Bordered card with a checkbox (opportunity types, notification channels). */
export function ChoiceCard({ checked, onChange, children, className }: { checked: boolean; onChange: (v: boolean) => void; children: ReactNode; className?: string }) {
  return (
    <label className={cn("flex cursor-pointer items-center gap-2.5 rounded-field border p-3.5 transition-colors", checked ? "border-brand bg-page" : "border-line bg-surface hover:border-faint", className)}>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="peer sr-only" />
      <span className={cn("flex size-[18px] shrink-0 items-center justify-center rounded-md border peer-focus-visible:shadow-focus", checked ? "border-brand bg-brand" : "border-faint")}>
        {/* eslint-disable-next-line @next/next/no-img-element -- decorative check */}
        {checked && <img src="/icons/check-white-11.svg" alt="" width={11} height={11} />}
      </span>
      {children}
    </label>
  );
}

/** Small mono uppercase section label ("UPLOAD YOUR CV (OPTIONAL)"). */
export function SectionLabel({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cn("font-mono text-[11px] tracking-[1px] text-muted uppercase", className)}>{children}</p>;
}
