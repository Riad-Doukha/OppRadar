import type { Metadata } from "next";
import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { NotificationsPage } from "@/components/notifications/notifications-page";

export const metadata: Metadata = { title: "Notifications" };

export default function Page() {
  return (
    <Suspense>
      <AppShell>
        <NotificationsPage />
      </AppShell>
    </Suspense>
  );
}
