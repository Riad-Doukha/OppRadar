import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { PremiumPage } from "@/components/premium/premium-page";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("premium");

export default function Page() {
  return (
    <Suspense>
      <AppShell>
        <PremiumPage />
      </AppShell>
    </Suspense>
  );
}
