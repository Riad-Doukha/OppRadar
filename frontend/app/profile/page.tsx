import type { Metadata } from "next";
import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { ProfilePage } from "@/components/profile/profile-page";

export const metadata: Metadata = { title: "My profile" };

export default function Page() {
  return (
    <Suspense>
      <AppShell>
        <ProfilePage />
      </AppShell>
    </Suspense>
  );
}
