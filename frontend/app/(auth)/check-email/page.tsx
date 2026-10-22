import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthCard } from "@/components/auth/auth-card";

import { CheckEmail } from "./check-email";

export const metadata: Metadata = { title: "Check your email" };

export default function CheckEmailPage() {
  return (
    <AuthCard>
      <Suspense>
        <CheckEmail />
      </Suspense>
    </AuthCard>
  );
}
