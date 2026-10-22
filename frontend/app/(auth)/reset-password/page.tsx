import type { Metadata } from "next";

import { AuthCard } from "@/components/auth/auth-card";

import { ResetPassword } from "./reset-password";

export const metadata: Metadata = { title: "Choose a new password" };

// Reached from the e-mail link: /auth/callback has already signed the user in.
export default function ResetPasswordPage() {
  return (
    <AuthCard>
      <ResetPassword />
    </AuthCard>
  );
}
