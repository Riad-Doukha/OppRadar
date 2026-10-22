// Client-side auth rules mirrored from supabase/config.toml, and the copy for
// Supabase Auth errors (its raw messages are not meant for users).

export const RESEND_SECONDS = 60; // auth.email.max_frequency
export const RESET_LINK_MINUTES = 30; // auth.email.otp_expiry

export function passwordProblem(password: string): string | null {
  if (password.length < 8) return "Use at least 8 characters.";
  if (!/\d/.test(password)) return "Add at least one number.";
  if (!/[a-z]/i.test(password)) return "Add at least one letter.";
  return null;
}

/** 0–4 bars for the strength meter under the sign-up password. */
export function passwordStrength(password: string): { score: number; label: string } {
  if (!password) return { score: 0, label: "" };
  let score = 0;
  if (password.length >= 8) score++;
  if (/\d/.test(password) && /[a-z]/i.test(password)) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/[^a-z0-9]/i.test(password) || password.length >= 14) score++;
  return { score, label: ["too short", "weak", "fair", "good", "strong"][score] };
}

export function authErrorMessage(error: { message?: string; code?: string; status?: number }): string {
  const code = error.code ?? "";
  const message = (error.message ?? "").toLowerCase();
  if (code === "invalid_credentials" || message.includes("invalid login credentials"))
    return "Wrong email or password. Try again or reset your password.";
  if (code === "user_already_exists" || message.includes("already registered"))
    return "An account with this email already exists. Log in instead.";
  if (code === "weak_password") return "Choose a stronger password: 8+ characters with a number.";
  if (code === "over_email_send_rate_limit" || error.status === 429)
    return "Too many attempts. Wait a minute and try again.";
  if (code === "same_password") return "Your new password must be different from the old one.";
  if (message.includes("fetch")) return "We couldn't reach the server. Check your connection.";
  return "Something went wrong. Please try again.";
}
