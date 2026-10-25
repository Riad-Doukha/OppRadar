"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { api } from "@/lib/api/client";
import { createClient } from "@/lib/supabase/client";

type DemoSession = { access_token: string; refresh_token: string };

/** "Try the demo instead →": signs in to the shared read-only demo account. */
export function DemoLink() {
  const t = useTranslations("auth.demo");
  const router = useRouter();
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");

  async function start() {
    setState("loading");
    try {
      const tokens = await api<DemoSession>("/auth/demo", { method: "POST" });
      const { error } = await createClient().auth.setSession(tokens);
      if (error) throw error;
      router.push("/dashboard");
      router.refresh();
    } catch {
      setState("error");
    }
  }

  return (
    <div className="flex flex-col items-center pt-2">
      <button type="button" onClick={start} disabled={state === "loading"} className="text-sm font-bold text-brand hover:text-brand-strong disabled:opacity-60">
        {state === "loading" ? t("opening") : <>{t("try")} <span className="inline-block rtl:-scale-x-100">→</span></>}
      </button>
      {state === "error" && <p className="pt-1 text-xs text-danger">{t("unavailable")}</p>}
    </div>
  );
}
