import type { Metadata } from "next";
import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { OpportunityDetail } from "@/components/dashboard/opportunity-detail";

export const metadata: Metadata = { title: "Opportunity" };

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
