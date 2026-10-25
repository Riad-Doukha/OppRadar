import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { SettingsPage } from "@/components/settings/settings-page";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("settings");

export default function Page() {
  return (
    <Suspense>
      <AppShell>
        <SettingsPage />
      </AppShell>
    </Suspense>
  );
}
