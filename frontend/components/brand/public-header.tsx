import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { LanguageMenu } from "@/components/app/language-menu";
import { ThemeToggle } from "@/components/app/theme-toggle";
import { Logo } from "@/components/brand/logo";
import { ButtonLink } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Header of the public pages (landing, explore): links, language, theme, log in / sign up. */
export async function PublicHeader({ active }: { active: "home" | "explore" }) {
  const t = await getTranslations("landing");
  const te = await getTranslations("explore");
  const link = (on: boolean) => cn(on ? "font-bold text-ink" : "font-medium text-body hover:text-ink");
  return (
    <header className="sticky top-0 z-10 flex h-[60px] items-center justify-between gap-3 border-b border-line bg-surface px-4 md:h-[68px] md:px-10">
      <Logo />
      <nav className="hidden items-center gap-7 text-[15px] md:flex" aria-label={t("nav.how")}>
        <Link href="/explore" className={link(active === "explore")} aria-current={active === "explore" ? "page" : undefined}>
          {te("nav")}
        </Link>
        <Link href="/#how-it-works" className={link(false)}>
          {t("nav.how")}
        </Link>
        <Link href="/#privacy" className={link(false)}>
          {t("nav.privacy")}
        </Link>
      </nav>
      <div className="flex items-center gap-1 md:gap-3">
        <LanguageMenu />
        <ThemeToggle />
        <ButtonLink href="/login" variant="ghost" size="sm" className="px-3 md:px-5">
          {t("nav.logIn")}
        </ButtonLink>
        <ButtonLink href="/signup" size="sm" className="hidden md:inline-flex">
          {t("nav.start")}
        </ButtonLink>
      </div>
    </header>
  );
}
