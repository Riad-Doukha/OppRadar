// Public (browser-safe) configuration. Next inlines NEXT_PUBLIC_* at build
// time, so each variable must be referenced literally.
export const env = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
  supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
  // Shown on the legal pages only when set (no made-up address).
  contactEmail: process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? "",
  // Google Search Console "HTML tag" value: proves we own the site (meta tag in app/layout.tsx).
  googleSiteVerification: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION ?? "",
};
