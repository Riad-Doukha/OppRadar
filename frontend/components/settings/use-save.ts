"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { api, type Me } from "@/lib/api/client";

/**
 * Save one settings change right away (toggles and pickers have no Save
 * button). The screen updates optimistically from `optimistic(me)` and rolls
 * back if the API refuses. Returns the mutation for error display.
 */
export function useSave(path: "/me/onboarding/alerts" | "/me/settings") {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ body }: { body: object; optimistic?: (me: Me) => Me }) =>
      api<Me>(path, { method: "PATCH", body: JSON.stringify(body) }),
    onMutate: async ({ optimistic }) => {
      await qc.cancelQueries({ queryKey: ["me"] });
      const previous = qc.getQueryData<Me>(["me"]);
      if (previous && optimistic) qc.setQueryData(["me"], optimistic(previous));
      return { previous };
    },
    onError: (_e, _v, ctx) => ctx?.previous && qc.setQueryData(["me"], ctx.previous),
    onSuccess: (me) => qc.setQueryData(["me"], me),
  });
}
