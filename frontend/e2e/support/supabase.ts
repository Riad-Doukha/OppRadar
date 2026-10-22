// Service-role helper for the journey test: creates and deletes a throwaway
// account. Reads SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY from the repo's root
// .env (like the backend). Never use this in app code.
import path from "node:path";

import { loadEnvConfig } from "@next/env";
import { createClient } from "@supabase/supabase-js";

loadEnvConfig(path.resolve(__dirname, "..", "..", ".."), false, undefined, true);

const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY || "";

export const hasSupabase = Boolean(url && serviceKey);

const admin = () => createClient(url, serviceKey, { auth: { persistSession: false, autoRefreshToken: false } });

export async function createUser(fullName: string) {
  const email = `e2e-journey-${Date.now().toString(36)}@example.com`;
  const password = `E2e-${crypto.randomUUID()}9`;
  const { data, error } = await admin().auth.admin.createUser({
    email,
    password,
    email_confirm: true,
    user_metadata: { full_name: fullName, terms_accepted: true },
  });
  if (error) throw error;
  return { id: data.user.id, email, password };
}

/** Delete the account if the test didn't (cascade removes its rows). */
export async function deleteUser(id: string) {
  const { error } = await admin().auth.admin.deleteUser(id);
  if (error && !/not.?found/i.test(error.message)) throw error;
}
