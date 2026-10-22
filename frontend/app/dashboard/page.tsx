import type { Metadata } from "next";

import { SignedInPlaceholder } from "@/components/auth/signed-in-placeholder";

export const metadata: Metadata = { title: "Your matches" };

export default function DashboardPage() {
  return <SignedInPlaceholder title="Your matches" />;
}
