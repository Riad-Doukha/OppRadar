import { Suspense } from "react";

import { OnboardingWizard } from "@/components/onboarding/wizard";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("onboarding");

export default function OnboardingPage() {
  return (
    <Suspense>
      <OnboardingWizard />
    </Suspense>
  );
}
