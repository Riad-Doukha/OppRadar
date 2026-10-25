import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { NotificationsPage } from "@/components/notifications/notifications-page";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("notifications");

export default function Page() {
  return (
    <Suspense>
      <AppShell>
        <NotificationsPage />
      </AppShell>
    </Suspense>
  );
}
