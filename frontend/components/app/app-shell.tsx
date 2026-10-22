"use client";

import { useQuery } from "@tanstack/react-query";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import { Logo } from "@/components/brand/logo";
import { NotificationBell } from "@/components/notifications/bell";
import { useNotificationSummary } from "@/lib/notifications";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type Me } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";

type NavItem = { label: string; icon: string; href?: string; soon?: boolean };

const NAV: NavItem[] = [
  { label: "Dashboard", icon: "nav-dashboard", href: "/dashboard" },
  { label: "Ask the agent", icon: "nav-ask", soon: true },
  { label: "Notifications", icon: "nav-notifications", href: "/notifications" },
  { label: "My profile", icon: "nav-profile", href: "/profile" },
  { label: "Applications", icon: "nav-applications", soon: true },
];
const NAV_MORE: NavItem[] = [
  { label: "Premium", icon: "nav-premium", soon: true },
  { label: "Settings", icon: "nav-settings", href: "/settings" },
];

export const initialsOf = (name: string) =>
  name.split(/\s+/).filter(Boolean).map((w) => w[0]).slice(0, 2).join("").toUpperCase() || "?";

/** Signed-in layout from the Figma dashboard: top bar + left nav (desktop). */
export function AppShell({ children }: { children: ReactNode }) {
  const me = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/me") });
  return (
    <div className="min-h-dvh bg-page">
      <a
        href="#main"
        className="sr-only z-50 rounded-field bg-surface px-4 py-2 text-sm font-bold text-brand shadow-float focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      <TopBar me={me.data} />
      <div className="mx-auto flex max-w-[1440px]">
        <aside className="sticky top-16 hidden h-[calc(100dvh-4rem)] w-[264px] shrink-0 flex-col gap-5 overflow-y-auto py-6 pr-4 pl-6 lg:flex">
          <Nav items={NAV} />
          <div className="h-px bg-line" />
          <Nav items={NAV_MORE} />
          <div className="rounded-card border border-line bg-surface p-4 shadow-[0_1px_1.5px_rgb(30_17_62/0.05)]">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-signal px-3 py-1.5 text-xs font-bold text-body">
              <Image src="/icons/lock-dark.svg" alt="" width={13} height={13} />
              Only you can see this
            </span>
            <p className="pt-2 text-xs text-muted">Your profile is private. We never post or message on your behalf.</p>
          </div>
        </aside>
        <main id="main" tabIndex={-1} className="min-w-0 flex-1 px-4 pt-6 pb-12 outline-none sm:px-6 lg:pt-7 lg:pr-10 lg:pl-6">
          {children}
        </main>
      </div>
    </div>
  );
}

function Nav({ items }: { items: NavItem[] }) {
  const pathname = usePathname();
  const unread = useNotificationSummary().data?.unread ?? 0;
  return (
    <nav className="flex flex-col gap-1" aria-label="Main">
      {items.map((item) => {
        const active = item.href && pathname === item.href.split("?")[0];
        const body = (
          <>
            <NavIcon name={item.icon} className={active ? "text-brand-strong" : "text-body"} />
            <span className={cn("text-[15px]", active ? "font-bold text-brand-strong" : "font-medium text-body")}>{item.label}</span>
            {item.soon && <span className="ml-auto rounded-full bg-surface px-2 py-0.5 font-mono text-[10px] text-muted">soon</span>}
            {item.href === "/notifications" && unread > 0 && (
              <span className={cn("ml-auto rounded-full bg-surface px-[7px] py-0.5 font-mono text-[11px]", active ? "font-bold text-brand-strong" : "text-body")}>{unread}</span>
            )}
          </>
        );
        const cls = cn("flex h-11 items-center gap-3 rounded-field px-3.5", active ? "bg-brand-soft" : item.href && "hover:bg-surface");
        return item.href ? (
          <Link key={item.label} href={item.href} className={cls} aria-current={active ? "page" : undefined}>
            {body}
          </Link>
        ) : (
          <span key={item.label} className={cn(cls, "cursor-default opacity-70")} title="Coming soon">
            {body}
          </span>
        );
      })}
    </nav>
  );
}

/**
 * The Figma nav icons are single-colour line icons; drawing them as a mask
 * filled with currentColor lets the active item's icon turn purple while the
 * rest stay grey (the SVG files themselves have one fixed stroke colour).
 */
function NavIcon({ name, className }: { name: string; className?: string }) {
  const url = `url(/icons/${name}.svg)`;
  return (
    <span
      aria-hidden
      className={cn("size-[18px] shrink-0 bg-current", className)}
      style={{ maskImage: url, WebkitMaskImage: url, maskSize: "contain", WebkitMaskSize: "contain", maskRepeat: "no-repeat", WebkitMaskRepeat: "no-repeat" }}
    />
  );
}

function TopBar({ me }: { me?: Me }) {
  const router = useRouter();
  const params = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");

  function search(e: FormEvent) {
    e.preventDefault();
    const query = q.trim();
    router.push(query ? `/dashboard?q=${encodeURIComponent(query)}` : "/dashboard");
  }

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-line bg-surface px-4 sm:gap-6 sm:px-8">
      <Logo href="/dashboard" />
      <form onSubmit={search} role="search" className="hidden max-w-[420px] flex-1 items-center gap-2.5 rounded-field bg-page px-3.5 focus-within:shadow-focus sm:flex">
        <Image src="/icons/search.svg" alt="" width={16} height={16} />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search opportunities"
          aria-label="Search opportunities"
          className="h-10 min-w-0 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-faint"
        />
      </form>
      <div className="ml-auto flex items-center gap-2">
        <NotificationBell me={me} />
        <Link href="/settings" className="hidden size-10 items-center justify-center rounded-field hover:bg-page sm:flex" aria-label="Settings">
          <Image src="/icons/gear.svg" alt="" width={20} height={20} />
        </Link>
        <AccountMenu me={me} />
      </div>
    </header>
  );
}

function AccountMenu({ me }: { me?: Me }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
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

  async function logOut() {
    await createClient().auth.signOut();
    router.push("/");
    router.refresh();
  }

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="Account menu"
        className="flex size-[38px] items-center justify-center rounded-full bg-brand-soft text-sm font-bold text-brand-strong"
      >
        {me ? initialsOf(me.full_name || me.email) : <Skeleton className="size-5 rounded-full bg-brand/20" />}
      </button>
      {open && (
        <div role="menu" className="absolute right-0 mt-2 w-60 rounded-card border border-line bg-surface p-2 shadow-float">
          {me && (
            <div className="border-b border-line px-3 pt-1 pb-2.5">
              <p className="truncate text-sm font-bold text-ink">{me.full_name || "Your account"}</p>
              <p className="truncate text-xs text-muted">{me.is_demo ? "Read-only demo" : me.email}</p>
            </div>
          )}
          <Link role="menuitem" href="/dashboard" className="block rounded-lg px-3 py-2 text-sm text-body hover:bg-page lg:hidden" onClick={() => setOpen(false)}>
            Dashboard
          </Link>
          <Link role="menuitem" href="/profile" className="block rounded-lg px-3 py-2 text-sm text-body hover:bg-page" onClick={() => setOpen(false)}>
            My profile
          </Link>
          <Link role="menuitem" href="/settings" className="block rounded-lg px-3 py-2 text-sm text-body hover:bg-page" onClick={() => setOpen(false)}>
            Settings
          </Link>
          <button role="menuitem" type="button" onClick={logOut} className="block w-full rounded-lg px-3 py-2 text-left text-sm text-body hover:bg-page">
            {me?.is_demo ? "Leave the demo" : "Log out"}
          </button>
        </div>
      )}
    </div>
  );
}
