import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { getTranslations } from "next-intl/server";


import { CountUp } from "@/components/brand/count-up";
import { Logo } from "@/components/brand/logo";
import { PublicHeader } from "@/components/brand/public-header";
import { RadarParallax } from "@/components/brand/radar-parallax";
import { ButtonLink } from "@/components/ui/button";

const STATS = [
  { value: "+47", label: "sources" },
  { value: null, label: "languages" },
  { value: "0", label: "sent" },
] as const;

const PROMISES = [
  { icon: "/icons/lock-light.svg", text: "p1" },
  { icon: "/icons/lock-light.svg", text: "p2" },
  { icon: "/icons/external-light.svg", text: "p3" },
] as const;

const strong = (chunks: React.ReactNode) => <strong className="text-ink">{chunks}</strong>;

export default async function LandingPage({ searchParams }: { searchParams: Promise<{ deleted?: string }> }) {
  const { deleted } = await searchParams;
  const t = await getTranslations("landing");
  const tl = await getTranslations("legal");
  const te = await getTranslations("explore");
  return (
    <div className="min-h-dvh bg-page">
      <PublicHeader active="home" />

      {deleted && (
        <p role="status" className="bg-success-tint px-4 py-3 text-center text-sm font-bold text-success">
          {t("deleted")}
        </p>
      )}
      <main>
        {/* Hero */}
        <section className="mx-auto flex max-w-[1440px] flex-col gap-10 px-4 pt-8 pb-14 md:flex-row md:items-center md:gap-14 md:px-16 md:pt-[72px]">
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-[34px] leading-[1.1] font-extrabold tracking-[-1px] text-ink md:pt-5 md:text-[52px]">
              {t.rich("hero.title", { br: () => <br />, brand: (c) => <span className="text-brand">{c}</span> })}
            </h1>
            <p className="max-w-[481px] pt-4 text-base leading-[27px] text-body md:text-lg">
              {t("hero.lead")}
            </p>
            <div className="flex flex-col gap-3 pt-7 sm:flex-row">
              <ButtonLink href="/signup" size="hero">
                {t("hero.cta")}
              </ButtonLink>
              <ButtonLink href="/login" variant="outline" size="hero" className="px-[22px]">
                {t("hero.login")}
              </ButtonLink>
            </div>
            {/* Plain GET form: works before JavaScript loads. */}
            <form action="/explore" role="search" className="mt-5 flex max-w-[481px] items-center gap-2 rounded-field border border-line bg-surface px-3 py-1.5 focus-within:shadow-focus">
              <Image src="/icons/search.svg" alt="" width={16} height={16} />
              <input
                name="q"
                maxLength={200}
                placeholder={te("heroPlaceholder")}
                aria-label={te("heroSearch")}
                className="h-9 min-w-0 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-faint"
              />
              <button type="submit" className="rounded-lg px-3 py-1.5 text-sm font-bold text-brand hover:bg-brand-soft">
                {te("searchButton")}
              </button>
            </form>
          </div>

          <RadarPreview />
        </section>

        {/* Stats */}
        <section className="flex justify-center gap-6 px-4 pb-14 md:gap-12 md:px-16" aria-label={t("stats.label")}>
          {STATS.map((s) => (
            <div key={s.label} className="flex flex-col items-center text-center">
              <p dir="ltr" className="pt-1.5 font-mono text-xl font-semibold text-ink md:text-[28px]">{s.value ?? t("stats.languagesValue")}</p>
              <p className="max-w-[110px] text-xs text-muted md:max-w-none">{t(`stats.${s.label}`)}</p>
            </div>
          ))}
        </section>

        {/* How it works */}
        <section id="how-it-works" className="mx-auto max-w-[1440px] scroll-mt-20 px-4 pb-16 md:px-16">
          <h2 className="font-display text-[26px] font-bold text-ink">{t("how.title")}</h2>
          <p className="pt-1.5 text-sm text-muted">{t("how.sub")}</p>
          <ol className="grid gap-5 pt-5 md:grid-cols-3">
            <Step n={1} title={t("how.s1Title")}>
              {t.rich("how.s1", { strong })}
            </Step>
            <Step n={2} title={t("how.s2Title")}>
              {t("how.s2")}
            </Step>
            <Step n={3} title={t("how.s3Title")}>
              {t.rich("how.s3", { strong })}
            </Step>
          </ol>
        </section>
      </main>

      {/* Privacy band + footer */}
      <footer className="bg-night">
        <section
          id="privacy"
          className="mx-auto flex max-w-[1440px] scroll-mt-20 flex-col gap-6 px-4 py-11 text-center md:flex-row md:items-center md:justify-between md:px-16 md:text-start"
        >
          <div className="md:max-w-[560px]">
            <h2 className="font-display text-xl font-bold tracking-[-0.5px] text-white md:text-[28px] md:leading-[33.6px]">
              {t("privacy.title")}
            </h2>
            <p className="pt-2 text-[13px] text-on-night md:text-[15px]">
              {t("privacy.body")}
            </p>
          </div>
          <ul className="hidden max-w-[460px] flex-wrap gap-2 md:flex">
            {PROMISES.map((p) => (
              <li key={p.text} className="flex items-center gap-1.5 rounded-full bg-night-raised px-3 py-1.5 text-xs font-bold text-on-night-strong">
                <Image src={p.icon} alt="" width={13} height={13} />
                {t(`privacy.${p.text}`)}
              </li>
            ))}
          </ul>
        </section>
        <div className="mx-auto flex max-w-[1440px] items-center justify-center px-4 py-8 md:justify-between md:px-16">
          <span className="hidden md:inline-flex">
            <Logo tone="yellow" />
          </span>
          <div className="flex flex-col items-center gap-1.5 md:items-end">
            <Link href="/submit" className="text-[13px] font-bold text-on-night-strong underline-offset-4 hover:underline">
              {t("orgs")} <span className="inline-block rtl:-scale-x-100">→</span>
            </Link>
            <p className="text-[13px] text-on-night">{t("footer")}</p>
            <p className="flex gap-4 text-[13px]">
              <Link href="/terms" className="text-on-night underline-offset-4 hover:underline">{tl("terms.title")}</Link>
              <Link href="/privacy" className="text-on-night underline-offset-4 hover:underline">{tl("privacy.title")}</Link>
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="flex flex-col rounded-card border border-line bg-surface p-6">
      <span className="flex size-10 items-center justify-center rounded-field bg-brand-soft font-mono text-base font-semibold text-brand-strong">
        {n}
      </span>
      <h3 className="pt-3.5 font-display text-xl font-bold text-ink">{title}</h3>
      <p className="pt-1.5 text-sm text-body">{children}</p>
    </li>
  );
}

/** Radar disc with an example match card (illustration, not live data). */
async function RadarPreview() {
  const t = await getTranslations("landing.sample");
  return (
    <RadarParallax className="relative mx-auto w-full max-w-[520px] shrink-0 md:w-[520px]">
      <div className="radar-disc parallax-back relative mx-auto aspect-square w-[78%] max-w-[420px] overflow-hidden rounded-full md:w-[420px]">
        <div className="absolute inset-[6.67%] rounded-full border border-white/25">
          <div className="absolute inset-[15.4%] rounded-full border border-white/25" />
          <div className="absolute inset-[30.8%] rounded-full border border-white/25" />
          <div className="absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 bg-white/25" />
          <div className="absolute inset-x-0 top-1/2 h-0.5 -translate-y-1/2 bg-white/25" />
        </div>
        <div className="radar-sweep absolute inset-0 rounded-full" />
        <span className="radar-blip absolute top-[22.9%] start-[71%] size-[18px] rounded-full bg-signal shadow-[0_0_0_6px_rgb(250_252_82/0.35)]" />
        <span className="radar-blip absolute top-[66.2%] start-[21%] size-3 rounded-full bg-signal shadow-[0_0_0_5px_rgb(250_252_82/0.28)] [animation-delay:0.8s]" />
        <span className="radar-blip absolute top-[42.9%] start-[42.9%] size-2.5 rounded-full bg-signal shadow-[0_0_0_4px_rgb(250_252_82/0.22)] [animation-delay:1.6s]" />
      </div>

      <div className="radar-float parallax-front relative -mt-14 rounded-card border border-line bg-surface p-[22px] shadow-float md:absolute md:top-[239px] md:-start-7 md:mt-0 md:w-[340px]">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex gap-2">
              <span className="flex h-7 items-center gap-1.5 rounded-full bg-success-soft px-3 text-[13px] font-bold text-success">
                <Image src="/icons/check-circle-green.svg" alt="" width={15} height={15} />
                {t("eligible")}
              </span>
              <span className="hidden h-7 items-center gap-1.5 rounded-full bg-signal px-3 text-xs font-bold text-on-signal md:flex">
                <Image src="/icons/sparkle-purple.svg" alt="" width={14} height={14} />
                {t("new")}
              </span>
            </div>
            <p className="pt-2 text-base font-bold text-ink">{t("title")}</p>
            <p className="pt-1 text-[13px] text-muted">{t("org")}</p>
          </div>
          <div className="relative size-14 shrink-0">
            <Image src="/icons/score-ring-94.svg" alt="" width={56} height={56} />
            <CountUp to={94} className="absolute inset-0 flex items-center justify-center font-mono text-[13px] font-semibold text-ink" />
          </div>
        </div>
        <p className="flex items-center gap-1.5 pt-3 text-[13px] font-bold text-warning">
          <Image src="/icons/clock-orange.svg" alt="" width={15} height={15} />
          {t("closes")}
        </p>
      </div>
    </RadarParallax>
  );
}

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("landing.meta");
  return { title: { absolute: t("title") } };
}
