import type { Metadata } from "next";
import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { ApplyPage } from "@/components/apply/apply-page";

export const metadata: Metadata = { title: "Apply assistant" };

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
