import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { ReservedPage } from "@/components/premium/reserved-page";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("premiumReserved");

export default function Page() {
  return (
    <Suspense>
      <AppShell>
        <ReservedPage />
      </AppShell>
    </Suspense>
  );
}
