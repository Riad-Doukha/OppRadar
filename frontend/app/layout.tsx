import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OppRadar",
  description: "AI-powered radar for internships, jobs and scholarships.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
