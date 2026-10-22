import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { SubmitPage } from "@/components/submit/submit-page";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("submit");

export default function Page() {
  return (
    <Suspense>
      <AppShell>
        <SubmitPage />
      </AppShell>
    </Suspense>
  );
}
