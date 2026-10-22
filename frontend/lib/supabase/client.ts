import { createBrowserClient } from "@supabase/ssr";

import { env } from "@/lib/env";

/** Supabase client for Client Components (session lives in cookies). */
export function createClient() {
  return createBrowserClient(env.supabaseUrl, env.supabaseAnonKey);
}
