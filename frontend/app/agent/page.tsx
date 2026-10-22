import type { Metadata } from "next";
import { Suspense } from "react";

import { AgentPage } from "@/components/agent/agent-page";
import { AppShell } from "@/components/app/app-shell";

export const metadata: Metadata = { title: "Ask the agent" };

export default function Page() {
  return (
    <Suspense>
      <AppShell>
        <AgentPage />
      </AppShell>
    </Suspense>
  );
}
