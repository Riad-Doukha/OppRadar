import { Suspense } from "react";

import { AuthCard } from "@/components/auth/auth-card";

import { CheckEmail } from "./check-email";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("checkEmail");

export default function CheckEmailPage() {
  return (
    <AuthCard>
      <Suspense>
        <CheckEmail />
      </Suspense>
    </AuthCard>
  );
}
