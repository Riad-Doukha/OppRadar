// Client-side auth rules mirrored from supabase/config.toml, and which message
// to show for Supabase Auth errors (its raw messages are not meant for users).
// Functions return message keys under `auth.*`; components translate them.

export const RESEND_SECONDS = 60; // auth.email.max_frequency
export const RESET_LINK_MINUTES = 30; // auth.email.otp_expiry

export type PasswordProblem = "short" | "number" | "letter";

export function passwordProblem(password: string): PasswordProblem | null {
  if (password.length < 8) return "short";
  if (!/\d/.test(password)) return "number";
  if (!/[a-z]/i.test(password)) return "letter";
  return null;
}

/** 0–4 bars for the strength meter under the sign-up password (auth.rules.strength.<score>). */
export function passwordStrength(password: string): 0 | 1 | 2 | 3 | 4 | null {
  if (!password) return null;
  let score = 0;
  if (password.length >= 8) score++;
  if (/\d/.test(password) && /[a-z]/i.test(password)) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/[^a-z0-9]/i.test(password) || password.length >= 14) score++;
  return score as 0 | 1 | 2 | 3 | 4;
}

export type AuthError = "invalidCredentials" | "exists" | "weakPassword" | "rateLimit" | "samePassword" | "network" | "generic";

export function authError(error: { message?: string; code?: string; status?: number }): AuthError {
  const code = error.code ?? "";
  const message = (error.message ?? "").toLowerCase();
  if (code === "invalid_credentials" || message.includes("invalid login credentials")) return "invalidCredentials";
  if (code === "user_already_exists" || message.includes("already registered")) return "exists";
  if (code === "weak_password") return "weakPassword";
  if (code === "over_email_send_rate_limit" || error.status === 429) return "rateLimit";
  if (code === "same_password") return "samePassword";
  if (message.includes("fetch")) return "network";
  return "generic";
}
