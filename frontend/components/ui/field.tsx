"use client";

import { useTranslations } from "next-intl";
import { useId, useState, type ComponentProps, type ReactNode } from "react";

import { cn } from "@/lib/utils";

const inputBase =
  "h-11 w-full rounded-field border bg-surface px-3.5 text-[15px] text-ink placeholder:text-faint outline-none transition-shadow focus:border-brand focus:shadow-focus";

type FieldProps = {
  label: string;
  /** Right-aligned element on the label row (e.g. "Forgot password?"). */
  aside?: ReactNode;
  hint?: ReactNode;
  error?: string | boolean;
  children: (props: { id: string; describedBy?: string; invalid: boolean }) => ReactNode;
};

export function Field({ label, aside, hint, error, children }: FieldProps) {
  const id = useId();
  const hintId = `${id}-hint`;
  const invalid = Boolean(error);
  const message = typeof error === "string" ? error : hint;
  return (
    <div className="flex w-full flex-col">
      <div className="flex items-center justify-between pb-1.5">
        <label htmlFor={id} className="text-[13px] font-bold text-ink">
          {label}
        </label>
        {aside}
      </div>
      {children({ id, describedBy: message ? hintId : undefined, invalid })}
      {message && (
        <p id={hintId} className={cn("pt-1.5 text-xs", typeof error === "string" ? "text-danger" : "text-muted")}>
          {message}
        </p>
      )}
    </div>
  );
}

type InputProps = ComponentProps<"input"> & { invalid?: boolean; describedBy?: string };

export function Input({ className, invalid, describedBy, ...props }: InputProps) {
  return (
    <input
      aria-invalid={invalid || undefined}
      aria-describedby={describedBy}
      className={cn(inputBase, invalid ? "border-danger" : "border-line", className)}
      {...props}
    />
  );
}

/** Password input with the design's "Show / Hide" toggle. */
export function PasswordInput({ className, invalid, describedBy, ...props }: InputProps) {
  const t = useTranslations("common");
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input
        type={visible ? "text" : "password"}
        invalid={invalid}
        describedBy={describedBy}
        className={cn("pe-16", className)}
        {...props}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute inset-y-0 end-3.5 my-auto h-fit text-xs font-medium text-muted hover:text-ink"
        aria-label={visible ? t("hidePassword") : t("showPassword")}
      >
        {visible ? t("hide") : t("show")}
      </button>
    </div>
  );
}
