import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { ApplyPage } from "@/components/apply/apply-page";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("apply");

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <AppShell>
        <ApplyPage id={id} />
      </AppShell>
    </Suspense>
  );
}
