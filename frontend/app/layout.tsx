import type { Metadata, Viewport } from "next";
import { DM_Sans, IBM_Plex_Mono, Nunito } from "next/font/google";

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

export const metadata: Metadata = {
  title: { default: "OppRadar", template: "%s · OppRadar" },
  description:
    "Scholarships, internships, hackathons and camps — scanned daily, ranked by your profile.",
};

export const viewport: Viewport = {
  themeColor: "#8b34ff",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${dmSans.variable} ${plexMono.variable} ${display.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
