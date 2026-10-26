import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { LanguageMenu } from "@/components/app/language-menu";
import { ThemeToggle } from "@/components/app/theme-toggle";
import { Logo } from "@/components/brand/logo";
import { PublicMobileMenu, type HeaderLink } from "@/components/brand/public-mobile-menu";
import { ButtonLink } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Header of the public pages (landing, explore, legal): links, language, theme,
 * log in / sign up. Desktop shows them inline; phones get all of it in a drawer.
 */
export async function PublicHeader({ active }: { active: "home" | "explore" }) {
  const t = await getTranslations("landing");
  const te = await getTranslations("explore");
  const links: HeaderLink[] = [
    { href: "/explore", label: te("nav"), current: active === "explore" },
    { href: "/#how-it-works", label: t("nav.how") },
    { href: "/#features", label: t("nav.features") },
    { href: "/#faq", label: t("nav.faq") },
    { href: "/#privacy", label: t("nav.privacy") },
  ];
  const link = (on?: boolean) => cn(on ? "font-bold text-ink" : "font-medium text-body hover:text-ink");
  return (
    <header className="sticky top-0 z-10 flex h-[60px] items-center justify-between gap-3 border-b border-line bg-surface px-4 md:h-[68px] md:px-10">
      <Logo />
      <nav className="hidden items-center gap-7 text-[15px] md:flex" aria-label={t("nav.how")}>
        {links.map((l) => (
          <Link key={l.href} href={l.href} className={link(l.current)} aria-current={l.current ? "page" : undefined}>
            {l.label}
          </Link>
        ))}
      </nav>
      <div className="hidden items-center gap-3 md:flex">
        <LanguageMenu />
        <ThemeToggle />
        <ButtonLink href="/login" variant="ghost" size="sm" className="px-5">
          {t("nav.logIn")}
        </ButtonLink>
        <ButtonLink href="/signup" size="sm">
          {t("nav.start")}
        </ButtonLink>
      </div>
      <PublicMobileMenu links={links} logIn={t("nav.logIn")} start={t("nav.start")} />
    </header>
  );
}
