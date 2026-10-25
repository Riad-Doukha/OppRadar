import { env } from "@/lib/env";
import { createClient } from "@/lib/supabase/client";

import type { components } from "./schema";

export type Schemas = components["schemas"];
export type Me = Schemas["Me"];

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(typeof detail === "string" ? detail : `Request failed (${status})`);
  }
}

/** Browser-side fetch to the FastAPI backend with the user's Supabase token. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  const headers = new Headers(init.headers);
  if (session) headers.set("Authorization", `Bearer ${session.access_token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  const res = await fetch(`${env.apiUrl}${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.detail ?? res.statusText);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}
