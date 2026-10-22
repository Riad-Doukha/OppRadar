import { Suspense } from "react";

import { AgentPage } from "@/components/agent/agent-page";
import { AppShell } from "@/components/app/app-shell";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("agent");

export default function Page() {
  return (
    <Suspense>
      <AppShell>
        <AgentPage />
      </AppShell>
    </Suspense>
  );
}
