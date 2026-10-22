
import { AuthCard } from "@/components/auth/auth-card";

import { SignupForm } from "./signup-form";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("signup");

export default function SignupPage() {
  return (
    <AuthCard>
      <SignupForm />
    </AuthCard>
  );
}
