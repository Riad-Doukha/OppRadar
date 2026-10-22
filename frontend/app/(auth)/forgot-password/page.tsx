import type { Metadata } from "next";

import { AuthCard } from "@/components/auth/auth-card";

import { ForgotPassword } from "./forgot-password";

export const metadata: Metadata = { title: "Reset your password" };

export default function ForgotPasswordPage() {
  return (
    <AuthCard>
      <ForgotPassword />
    </AuthCard>
  );
}
