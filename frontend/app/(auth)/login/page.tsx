import type { Metadata } from "next";
import { Suspense } from "react";

import { AuthCard } from "@/components/auth/auth-card";

import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Log in" };

export default function LoginPage() {
  return (
    <AuthCard>
      <Suspense>
        <LoginForm />
      </Suspense>
    </AuthCard>
  );
}
