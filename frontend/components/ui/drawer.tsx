"use client";

import { Menu, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/** The ☰ button that opens a navigation drawer (phones and tablets). */
export function MenuButton({ open, onClick, className }: { open: boolean; onClick: () => void; className?: string }) {
  const t = useTranslations("common");
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={open}
      aria-haspopup="dialog"
      aria-label={t("openMenu")}
      className={cn("flex size-10 items-center justify-center rounded-field text-ink hover:bg-page", className)}
    >
      <Menu aria-hidden className="size-6" strokeWidth={1.75} />
    </button>
  );
}

/**
 * Side panel for navigation on small screens: a modal dialog that slides in
 * from the end side (right, or left in Arabic). Escape, the backdrop and the
 * close button close it; focus moves into it and back to the opener; the page
 * behind does not scroll.
 */
export function Drawer({ open, onClose, label, children }: { open: boolean; onClose: () => void; label: string; children: ReactNode }) {
  const t = useTranslations("common");
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";
    panel.current?.querySelector<HTMLElement>("a, button, input")?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key !== "Tab" || !panel.current) return;
      // Keep Tab inside the drawer while it is open.
      const items = [...panel.current.querySelectorAll<HTMLElement>("a[href], button:not([disabled]), input")];
      const first = items[0], last = items[items.length - 1];
      const wrapTo = e.shiftKey ? (document.activeElement === first ? last : null) : document.activeElement === last ? first : null;
      if (wrapTo) {
        e.preventDefault();
        wrapTo.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      opener?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50">
      <div aria-hidden className="absolute inset-0 bg-night/50 backdrop-blur-[2px]" onClick={onClose} />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        className="drawer-in absolute inset-y-0 end-0 flex w-[min(320px,86vw)] flex-col overflow-y-auto border-s border-line bg-surface shadow-float"
      >
        <div className="flex h-16 shrink-0 items-center justify-end border-b border-line px-3">
          <button
            type="button"
            onClick={onClose}
            aria-label={t("close")}
            className="flex size-10 items-center justify-center rounded-field text-ink hover:bg-page"
          >
            <X aria-hidden className="size-6" strokeWidth={1.75} />
          </button>
        </div>
        <div className="flex flex-1 flex-col gap-5 p-4">{children}</div>
      </div>
    </div>
  );
}
