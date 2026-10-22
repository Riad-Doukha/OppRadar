
import { AuthCard } from "@/components/auth/auth-card";

import { ResetPassword } from "./reset-password";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("resetPassword");

// Reached from the e-mail link: /auth/callback has already signed the user in.
export default function ResetPasswordPage() {
  return (
    <AuthCard>
      <ResetPassword />
    </AuthCard>
  );
}
