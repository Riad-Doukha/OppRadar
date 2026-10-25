import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { LegalPage } from "@/components/legal/legal-page";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("legal"))("privacy.title") };
}

export default function Page() {
  return <LegalPage doc="privacy" />;
}
