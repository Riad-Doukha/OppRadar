// Credentials of a sign-up waiting for its email confirmation, kept ONLY in
// this tab's memory (never in storage): /check-email uses them to sign in by
// itself once the link is clicked, even on another device. A refresh or a new
// tab forgets them; the page then offers "Log in" instead.

type Pending = { email: string; password: string };

let pending: Pending | null = null;

export function rememberSignup(email: string, password: string) {
  pending = { email, password };
}

export function pendingSignup(email: string): Pending | null {
  return pending && pending.email.toLowerCase() === email.toLowerCase() ? pending : null;
}

export function forgetSignup() {
  pending = null;
}
