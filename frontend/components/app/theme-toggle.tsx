"use client";

import { Moon, Sun } from "lucide-react";
import { useTranslations } from "next-intl";

import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

/**
 * One-click light/dark switch. Both icons render and CSS picks one (dark:),
 * so the server HTML matches whatever the pre-paint theme script chose.
 * "System" stays available in Settings → Account → Theme.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const t = useTranslations("common.theme");
  const [, setTheme] = useTheme();
  const flip = () => setTheme(document.documentElement.classList.contains("dark") ? "light" : "dark");
  return (
    <button type="button" onClick={flip} className={cn("flex size-10 items-center justify-center rounded-field text-body hover:bg-page", className)}>
      <Moon aria-hidden className="size-5 dark:hidden" strokeWidth={1.75} />
      <Sun aria-hidden className="hidden size-5 dark:block" strokeWidth={1.75} />
      <span className="sr-only dark:hidden">{t("toDark")}</span>
      <span className="sr-only hidden dark:inline">{t("toLight")}</span>
    </button>
  );
}
