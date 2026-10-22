import path from "node:path";
import { fileURLToPath } from "node:url";

import nextEnv from "@next/env";

// The repo keeps one .env at its root (shared with the backend and AI), but
// Next.js only looks in frontend/. Read the root file and pass the public
// values through `env` — Next's dev server resets process.env after loading
// this config, so setting process.env alone does not reach the middleware.
// Only NEXT_PUBLIC_* values belong here: `env` is inlined into browser code.
// forceReload: @next/env caches its first load (frontend/), whatever the dir.
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { combinedEnv } = nextEnv.loadEnvConfig(root, process.env.NODE_ENV !== "production", undefined, true);
const pub = (key) => process.env[key] || combinedEnv[key] || "";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: pub("NEXT_PUBLIC_API_URL") || "http://localhost:8000",
    NEXT_PUBLIC_SUPABASE_URL: pub("NEXT_PUBLIC_SUPABASE_URL"),
    NEXT_PUBLIC_SUPABASE_ANON_KEY: pub("NEXT_PUBLIC_SUPABASE_ANON_KEY"),
  },
};

export default nextConfig;
