import type { Metadata } from "next";
import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { SettingsPage } from "@/components/settings/settings-page";

export const metadata: Metadata = { title: "Settings" };

export default function Page() {
  return (
    <Suspense>
      <AppShell>
        <SettingsPage />
      </AppShell>
    </Suspense>
  );
}
