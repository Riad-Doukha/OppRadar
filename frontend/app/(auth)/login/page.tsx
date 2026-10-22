import { Suspense } from "react";

import { AuthCard } from "@/components/auth/auth-card";

import { LoginForm } from "./login-form";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("login");

export default function LoginPage() {
  return (
    <AuthCard>
      <Suspense>
        <LoginForm />
      </Suspense>
    </AuthCard>
  );
}
