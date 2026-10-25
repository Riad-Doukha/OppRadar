import path from "node:path";
import { fileURLToPath } from "node:url";

import nextEnv from "@next/env";
import createNextIntlPlugin from "next-intl/plugin";

// The repo keeps one .env at its root (shared with the backend and AI), but
// Next.js only looks in frontend/. Read the root file and pass the public
// values through `env` — Next's dev server resets process.env after loading
// this config, so setting process.env alone does not reach the middleware.
// Only NEXT_PUBLIC_* values belong here: `env` is inlined into browser code.
// forceReload: @next/env caches its first load (frontend/), whatever the dir.
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { combinedEnv } = nextEnv.loadEnvConfig(root, process.env.NODE_ENV !== "production", undefined, true);
const pub = (key) => process.env[key] || combinedEnv[key] || "";

// No script-src policy: the theme script and Next's own inline scripts would
// need nonces. These directives block framing, plugins and form/base hijacks.
const SECURITY_HEADERS = [
  { key: "Content-Security-Policy", value: "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  ...(process.env.NODE_ENV === "production" ? [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" }] : []),
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  headers: async () => [{ source: "/:path*", headers: SECURITY_HEADERS }],
  env: {
    NEXT_PUBLIC_API_URL: pub("NEXT_PUBLIC_API_URL") || "http://localhost:8000",
    NEXT_PUBLIC_SUPABASE_URL: pub("NEXT_PUBLIC_SUPABASE_URL"),
    NEXT_PUBLIC_SUPABASE_ANON_KEY: pub("NEXT_PUBLIC_SUPABASE_ANON_KEY"),
    NEXT_PUBLIC_CONTACT_EMAIL: pub("NEXT_PUBLIC_CONTACT_EMAIL"),
  },
};

export default createNextIntlPlugin("./i18n/request.ts")(nextConfig);
