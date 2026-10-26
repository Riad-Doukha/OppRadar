import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getTranslations } from "next-intl/server";

import { dirOf, type Locale } from "@/i18n/config";

import { env } from "@/lib/env";
import { THEME_SCRIPT } from "@/lib/theme-script";

import { Providers } from "./providers";
import "./globals.css";

// Fonts are committed under app/fonts (SIL OFL 1.1, from Fontsource), so builds
// never download them: Google Fonts fetches at build time failed in CI.
const dmSans = localFont({
  src: "./fonts/dm-sans-latin-opsz-normal.woff2", // variable: weight + optical size
  weight: "100 1000",
  variable: "--font-dm-sans",
});

const plexMono = localFont({
  src: [
    { path: "./fonts/ibm-plex-mono-latin-500-normal.woff2", weight: "500" },
    { path: "./fonts/ibm-plex-mono-latin-600-normal.woff2", weight: "600" },
  ],
  variable: "--font-plex-mono",
});

// The design uses LT Saeada (commercial). Nunito is the stand-in until the
// licensed files are added under app/fonts.
const display = localFont({
  src: "./fonts/nunito-latin-wght-normal.woff2", // variable weight
  weight: "200 1000",
  variable: "--font-display-face",
});

// Arabic glyphs: DM Sans / Nunito / Plex Mono have none, so the font stacks in
// globals.css fall through to this face for Arabic text only.
const arabic = localFont({
  src: [
    { path: "./fonts/ibm-plex-sans-arabic-arabic-400-normal.woff2", weight: "400" },
    { path: "./fonts/ibm-plex-sans-arabic-arabic-500-normal.woff2", weight: "500" },
    { path: "./fonts/ibm-plex-sans-arabic-arabic-600-normal.woff2", weight: "600" },
    { path: "./fonts/ibm-plex-sans-arabic-arabic-700-normal.woff2", weight: "700" },
  ],
  variable: "--font-arabic",
  preload: false,
});

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("landing.meta");
  return {
    title: { default: "OppRadar", template: "%s · OppRadar" },
    description: t("description"),
    // Google Search Console ownership tag (Google sign-in branding needs it).
    ...(env.googleSiteVerification && { verification: { google: env.googleSiteVerification } }),
  };
}

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f2fc" },
    { media: "(prefers-color-scheme: dark)", color: "#120c22" },
  ],
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = (await getLocale()) as Locale;
  return (
    // suppressHydrationWarning: THEME_SCRIPT adds the `dark` class before React hydrates.
    <html lang={locale} dir={dirOf(locale)} className={`${dmSans.variable} ${plexMono.variable} ${display.variable} ${arabic.variable}`} suppressHydrationWarning>
      <body>
        {/* First in <body>, not <head>: still runs before anything paints, and browser
            extensions (e.g. antivirus) that inject scripts into <head> can't shift it. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
        <NextIntlClientProvider>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
