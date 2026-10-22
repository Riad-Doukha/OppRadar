import { Suspense } from "react";

import { AppShell } from "@/components/app/app-shell";
import { CheckoutPage } from "@/components/premium/checkout-page";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("premiumCheckout");

export default function Page() {
  return (
    <Suspense>
      <AppShell>
        <CheckoutPage />
      </AppShell>
    </Suspense>
  );
}
