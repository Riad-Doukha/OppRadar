
import { AuthCard } from "@/components/auth/auth-card";

import { ForgotPassword } from "./forgot-password";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("forgotPassword");

export default function ForgotPasswordPage() {
  return (
    <AuthCard>
      <ForgotPassword />
    </AuthCard>
  );
}
