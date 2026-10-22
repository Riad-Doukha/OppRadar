import { Suspense } from "react";

import { AdminPage } from "@/components/admin/admin-page";
import { AppShell } from "@/components/app/app-shell";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("admin");

export default function Page() {
  return (
    <Suspense>
      <AppShell>
        <AdminPage />
      </AppShell>
    </Suspense>
  );
}
