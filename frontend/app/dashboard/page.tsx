import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { Dashboard } from "@/components/dashboard/dashboard";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("dashboard");

export default function DashboardPage() {
  return (
    <Suspense>
      <AppShell>
        <Dashboard />
      </AppShell>
    </Suspense>
  );
}
