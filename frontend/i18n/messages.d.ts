// Type-checks every t("key") against the English messages (the source of truth).
import type { Locale } from "./config";

type Messages = {
  common: typeof import("../messages/en/common.json");
  landing: typeof import("../messages/en/landing.json");
  auth: typeof import("../messages/en/auth.json");
  onboarding: typeof import("../messages/en/onboarding.json");
  options: typeof import("../messages/en/options.json");
  shell: typeof import("../messages/en/shell.json");
  dashboard: typeof import("../messages/en/dashboard.json");
  opportunity: typeof import("../messages/en/opportunity.json");
  profile: typeof import("../messages/en/profile.json");
  settings: typeof import("../messages/en/settings.json");
  notifications: typeof import("../messages/en/notifications.json");
  agent: typeof import("../messages/en/agent.json");
  apply: typeof import("../messages/en/apply.json");
  applications: typeof import("../messages/en/applications.json");
  premium: typeof import("../messages/en/premium.json");
  submit: typeof import("../messages/en/submit.json");
  admin: typeof import("../messages/en/admin.json");
  explore: typeof import("../messages/en/explore.json");
  legal: typeof import("../messages/en/legal.json");
};

declare module "next-intl" {
  interface AppConfig {
    Locale: Locale;
    Messages: Messages;
  }
}
