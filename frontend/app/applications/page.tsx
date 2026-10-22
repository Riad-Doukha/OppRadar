import type { Metadata } from "next";
import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { ApplicationsPage } from "@/components/applications/applications-page";

export const metadata: Metadata = { title: "Applications" };

export default function Page() {
  return (
    <Suspense>
      <AppShell>
        <ApplicationsPage />
      </AppShell>
    </Suspense>
  );
}
