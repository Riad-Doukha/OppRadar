import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { env } from "@/lib/env";

// Pages that need a signed-in user, and auth pages a signed-in user skips.
const PROTECTED = ["/onboarding", "/dashboard", "/scan", "/opportunities", "/profile"];
const GUEST_ONLY = ["/login", "/signup"];

export async function middleware(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient(env.supabaseUrl, env.supabaseAnonKey, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (toSet) => {
        toSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        toSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
      },
    },
  });

  // Refreshes an expired access token, then verifies its signature locally
  // against the project's cached JWKS — no Auth round trip per navigation
  // (getUser() would ask Supabase every time).
  const { data } = await supabase.auth.getClaims();
  const user = data?.claims?.sub ? { id: data.claims.sub } : null;

  const { pathname, search } = request.nextUrl;
  const redirect = (to: string) => {
    const url = request.nextUrl.clone();
    url.pathname = to;
    url.search = "";
    if (to === "/login") url.searchParams.set("next", pathname + search);
    const res = NextResponse.redirect(url);
    response.cookies.getAll().forEach((c) => res.cookies.set(c));
    return res;
  };

  if (!user && PROTECTED.some((p) => pathname.startsWith(p))) return redirect("/login");
  if (user && GUEST_ONLY.some((p) => pathname.startsWith(p))) return redirect("/onboarding");
  return response;
}

export const config = {
  // Everything except static files and images.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|brand/|icons/|.*\\.(?:svg|png|jpg|jpeg|webp)$).*)"],
};
