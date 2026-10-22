import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { OpportunityDetail } from "@/components/dashboard/opportunity-detail";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("opportunity");

export default async function OpportunityPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <Suspense>
      <AppShell>
        <OpportunityDetail id={id} />
      </AppShell>
    </Suspense>
  );
}
