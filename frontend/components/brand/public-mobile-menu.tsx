"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { LanguageMenu } from "@/components/app/language-menu";
import { ThemeToggle } from "@/components/app/theme-toggle";
import { ButtonLink } from "@/components/ui/button";
import { Drawer, MenuButton } from "@/components/ui/drawer";
import { cn } from "@/lib/utils";

export type HeaderLink = { href: string; label: string; current?: boolean };

/** Phones: the whole public navbar (links, language, theme, log in / sign up) in a drawer. */
export function PublicMobileMenu({ links, logIn, start }: { links: HeaderLink[]; logIn: string; start: string }) {
  const t = useTranslations("common");
  const [open, setOpen] = useState(false);
  const close = () => setOpen(false);
  return (
    <div className="md:hidden">
      <MenuButton open={open} onClick={() => setOpen(true)} />
      <Drawer open={open} onClose={close} label={t("menu")}>
        <nav aria-label={t("menu")}>
          <ul className="flex flex-col gap-1">
            {links.map((l) => (
              <li key={l.href}>
                <Link
                  href={l.href}
                  onClick={close}
                  aria-current={l.current ? "page" : undefined}
                  className={cn("flex h-11 items-center rounded-field px-3 text-[15px]", l.current ? "bg-brand-soft font-bold text-brand-strong" : "font-medium text-ink hover:bg-page")}
                >
                  {l.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex items-center gap-2 border-y border-line py-3">
          <LanguageMenu />
          <ThemeToggle />
        </div>
        <div className="flex flex-col gap-2">
          <ButtonLink href="/signup" block onClick={close}>
            {start}
          </ButtonLink>
          <ButtonLink href="/login" variant="outline" block onClick={close}>
            {logIn}
          </ButtonLink>
        </div>
      </Drawer>
    </div>
  );
}
