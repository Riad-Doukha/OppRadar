import type { Metadata, Viewport } from "next";
import { DM_Sans, IBM_Plex_Mono, IBM_Plex_Sans_Arabic, Nunito } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getTranslations } from "next-intl/server";

import { dirOf, type Locale } from "@/i18n/config";

import { THEME_SCRIPT } from "@/lib/theme-script";

import { Providers } from "./providers";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  axes: ["opsz"],
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["500", "600"],
  variable: "--font-plex-mono",
});

// The design uses LT Saeada (commercial). Nunito is the stand-in until the
// licensed files are added under app/fonts and loaded with next/font/local.
const display = Nunito({
  subsets: ["latin"],
  weight: ["600", "700", "800"],
  variable: "--font-display-face",
});

// Arabic glyphs: DM Sans / Nunito / Plex Mono have none, so the font stacks in
// globals.css fall through to this face for Arabic text only.
const arabic = IBM_Plex_Sans_Arabic({
  subsets: ["arabic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-arabic",
  preload: false,
});

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("landing.meta");
  return { title: { default: "OppRadar", template: "%s · OppRadar" }, description: t("description") };
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
