"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { createClient } from "@/lib/supabase/client";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
        },
      }),
  );

  // Cached API data belongs to one account. Drop all of it whenever the
  // signed-in user changes (log in, log out, demo <-> real account), so no
  // screen shows — or autosaves — another account's profile.
  useEffect(() => {
    let currentUser: string | null | undefined;
    const {
      data: { subscription },
    } = createClient().auth.onAuthStateChange((_event, session) => {
      const next = session?.user.id ?? null;
      if (currentUser !== undefined && next !== currentUser) client.clear();
      currentUser = next;
    });
    return () => subscription.unsubscribe();
  }, [client]);

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
