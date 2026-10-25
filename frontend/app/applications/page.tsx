import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { ApplicationsPage } from "@/components/applications/applications-page";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("applications");

export default function Page() {
  return (
    <Suspense>
      <AppShell>
        <ApplicationsPage />
      </AppShell>
    </Suspense>
  );
}
