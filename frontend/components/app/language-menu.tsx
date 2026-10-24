"use client";

import { Check, Languages } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

import { LOCALES, LOCALE_NAMES, type Locale } from "@/i18n/config";
import { changeLocale } from "@/lib/locale-sync";
import { cn } from "@/lib/utils";

/** Globe button + EN / FR / AR menu. The choice is a cookie; a refresh re-renders in the new language. */
export function LanguageMenu({ className }: { className?: string }) {
  const t = useTranslations("common.language");
  const locale = useLocale() as Locale;
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [pending, start] = useTransition();
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  function choose(l: Locale) {
    setOpen(false);
    if (l === locale) return;
    start(async () => {
      await changeLocale(l);
      router.refresh();
    });
  }

  return (
    <div ref={box} className={cn("relative", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={t("change", { name: LOCALE_NAMES[locale] })}
        className={cn("flex h-10 items-center gap-1.5 rounded-field px-2.5 text-body hover:bg-page aria-expanded:bg-page", pending && "opacity-60")}
      >
        <Languages aria-hidden className="size-5" strokeWidth={1.75} />
        <span className="font-mono text-xs font-bold uppercase">{locale}</span>
      </button>
      {open && (
        <div role="menu" aria-label={t("label")} className="absolute end-0 z-30 mt-2 w-44 rounded-card border border-line bg-surface p-1.5 shadow-float">
          {LOCALES.map((l) => (
            <button
              key={l}
              role="menuitemradio"
              aria-checked={l === locale}
              type="button"
              lang={l}
              onClick={() => choose(l)}
              className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-start text-sm text-body hover:bg-page"
            >
              {LOCALE_NAMES[l]}
              {l === locale && <Check aria-hidden className="size-4 text-brand" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
