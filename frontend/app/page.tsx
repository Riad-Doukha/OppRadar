import Image from "next/image";

import { CountUp } from "@/components/brand/count-up";
import { Logo } from "@/components/brand/logo";
import { RadarParallax } from "@/components/brand/radar-parallax";
import { ButtonLink } from "@/components/ui/button";

const STATS = [
  { value: "+47", label: "official sources scanned daily" },
  { value: "AR·FR·EN", label: "sources in three languages" },
  { value: "0", label: "applications ever sent without you" },
];

const PROMISES = [
  { icon: "/icons/lock-light.svg", text: "Only you can see this" },
  { icon: "/icons/lock-light.svg", text: "Nothing is sent until you press Submit" },
  { icon: "/icons/external-light.svg", text: "Always verify on the official page" },
];

export default function LandingPage() {
  return (
    <div className="min-h-dvh bg-page">
      <header className="sticky top-0 z-10 flex h-[60px] items-center justify-between border-b border-line bg-surface px-4 md:h-[68px] md:px-10">
        <Logo />
        <nav className="hidden items-center gap-7 text-[15px] md:flex" aria-label="Main">
          <a href="#how-it-works" className="font-bold text-ink">
            How it works
          </a>
          <a href="#privacy" className="font-medium text-body hover:text-ink">
            Privacy
          </a>
        </nav>
        <div className="flex items-center gap-3">
          <ButtonLink href="/login" variant="ghost" size="sm" className="px-3 md:px-5">
            Log in
          </ButtonLink>
          <ButtonLink href="/signup" size="sm" className="hidden md:inline-flex">
            Start your scan
          </ButtonLink>
        </div>
      </header>

      <main>
        {/* Hero */}
        <section className="mx-auto flex max-w-[1440px] flex-col gap-10 px-4 pt-8 pb-14 md:flex-row md:items-center md:gap-14 md:px-16 md:pt-[72px]">
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-[34px] leading-[1.1] font-extrabold tracking-[-1px] text-ink md:pt-5 md:text-[52px]">
              Find opportunities
              <br />
              actually made <span className="text-brand">for you.</span>
            </h1>
            <p className="max-w-[481px] pt-4 text-base leading-[27px] text-body md:text-lg">
              Scholarships, internships, hackathons and camps — scanned daily, ranked by your profile, checked for
              eligibility before you ever open the page.
            </p>
            <div className="flex flex-col gap-3 pt-7 sm:flex-row">
              <ButtonLink href="/signup" size="hero">
                Start your scan — free
              </ButtonLink>
              <ButtonLink href="/login" variant="outline" size="hero" className="px-[22px]">
                Login
              </ButtonLink>
            </div>
          </div>

          <RadarPreview />
        </section>

        {/* Stats */}
        <section className="flex justify-center gap-6 px-4 pb-14 md:gap-12 md:px-16" aria-label="OppRadar in numbers">
          {STATS.map((s) => (
            <div key={s.label} className="flex flex-col items-center text-center">
              <p className="pt-1.5 font-mono text-xl font-semibold text-ink md:text-[28px]">{s.value}</p>
              <p className="max-w-[110px] text-xs text-muted md:max-w-none">{s.label}</p>
            </div>
          ))}
        </section>

        {/* How it works */}
        <section id="how-it-works" className="mx-auto max-w-[1440px] scroll-mt-20 px-4 pb-16 md:px-16">
          <h2 className="font-display text-[26px] font-bold text-ink">How it works</h2>
          <p className="pt-1.5 text-sm text-muted">Three steps, about two minutes.</p>
          <ol className="grid gap-5 pt-5 md:grid-cols-3">
            <Step n={1} title="Tell us about you">
              Field, year, skills, wilaya. Stored privately — used only to rank matches.{" "}
              <strong className="text-ink">Only you can see this.</strong>
            </Step>
            <Step n={2} title="We scan & match">
              The agent reads more than 47 official sources, scores every opportunity against your profile and checks
              eligibility — reasons included.
            </Step>
            <Step n={3} title="You apply, for real">
              We open the <strong className="text-ink">official page</strong> so you can verify every detail yourself.
              Nothing is sent until you press Submit.
            </Step>
          </ol>
        </section>
      </main>

      {/* Privacy band + footer */}
      <footer className="bg-night">
        <section
          id="privacy"
          className="mx-auto flex max-w-[1440px] scroll-mt-20 flex-col gap-6 px-4 py-11 text-center md:flex-row md:items-center md:justify-between md:px-16 md:text-left"
        >
          <div className="md:max-w-[560px]">
            <h2 className="font-display text-xl font-bold tracking-[-0.5px] text-white md:text-[28px] md:leading-[33.6px]">
              Your search stays yours.
            </h2>
            <p className="pt-2 text-[13px] text-on-night md:text-[15px]">
              We never sell your data, never email you without consent, and never submit anything on your behalf.
            </p>
          </div>
          <ul className="hidden max-w-[460px] flex-wrap gap-2 md:flex">
            {PROMISES.map((p) => (
              <li key={p.text} className="flex items-center gap-1.5 rounded-full bg-night-raised px-3 py-1.5 text-xs font-bold text-on-night-strong">
                <Image src={p.icon} alt="" width={13} height={13} />
                {p.text}
              </li>
            ))}
          </ul>
        </section>
        <div className="mx-auto flex max-w-[1440px] items-center justify-center px-4 py-8 md:justify-between md:px-16">
          <span className="hidden md:inline-flex">
            <Logo tone="yellow" />
          </span>
          <p className="text-[13px] text-on-night">Made in Algiers · English · DZD · v1.0</p>
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
function RadarPreview() {
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
        <span className="radar-blip absolute top-[22.9%] left-[71%] size-[18px] rounded-full bg-signal shadow-[0_0_0_6px_rgb(250_252_82/0.35)]" />
        <span className="radar-blip absolute top-[66.2%] left-[21%] size-3 rounded-full bg-signal shadow-[0_0_0_5px_rgb(250_252_82/0.28)] [animation-delay:0.8s]" />
        <span className="radar-blip absolute top-[42.9%] left-[42.9%] size-2.5 rounded-full bg-signal shadow-[0_0_0_4px_rgb(250_252_82/0.22)] [animation-delay:1.6s]" />
      </div>

      <div className="radar-float parallax-front relative -mt-14 rounded-card border border-line bg-surface p-[22px] shadow-float md:absolute md:top-[239px] md:-left-7 md:mt-0 md:w-[340px]">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex gap-2">
              <span className="flex h-7 items-center gap-1.5 rounded-full bg-success-soft px-3 text-[13px] font-bold text-success">
                <Image src="/icons/check-circle-green.svg" alt="" width={15} height={15} />
                Eligible
              </span>
              <span className="hidden h-7 items-center gap-1.5 rounded-full bg-signal px-3 text-xs font-bold text-brand-text md:flex">
                <Image src="/icons/sparkle-purple.svg" alt="" width={14} height={14} />
                New
              </span>
            </div>
            <p className="pt-2 text-base font-bold text-ink">Algiers Data Sprint 2026</p>
            <p className="pt-1 text-[13px] text-muted">Ministry of Higher Education</p>
          </div>
          <div className="relative size-14 shrink-0">
            <Image src="/icons/score-ring-94.svg" alt="" width={56} height={56} />
            <CountUp to={94} className="absolute inset-0 flex items-center justify-center font-mono text-[13px] font-semibold text-ink" />
          </div>
        </div>
        <p className="flex items-center gap-1.5 pt-3 text-[13px] font-bold text-warning">
          <Image src="/icons/clock-orange.svg" alt="" width={15} height={15} />
          Closes Mar 12 · 8 days left
        </p>
      </div>
    </RadarParallax>
  );
}

export const metadata = { title: { absolute: "OppRadar — opportunities actually made for you" } };
