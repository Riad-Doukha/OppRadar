import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { ProfilePage } from "@/components/profile/profile-page";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("profile");

export default function Page() {
  return (
    <Suspense>
      <AppShell>
        <ProfilePage />
      </AppShell>
    </Suspense>
  );
}
