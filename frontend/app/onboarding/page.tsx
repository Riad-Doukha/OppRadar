import type { Metadata } from "next";

import { SignedInPlaceholder } from "@/components/auth/signed-in-placeholder";

export const metadata: Metadata = { title: "Set up your profile" };

export default function OnboardingPage() {
  return <SignedInPlaceholder title="Set up your profile" />;
}
