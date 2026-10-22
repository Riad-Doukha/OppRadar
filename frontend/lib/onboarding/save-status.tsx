"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

import { api, type Me } from "@/lib/api/client";

export type SaveState = "saved" | "pending" | "saving" | "error" | "readonly";

const SaveStatusContext = createContext<{ state: SaveState; setState: (s: SaveState) => void; error: string | null; setError: (e: string | null) => void }>({
  state: "saved",
  setState: () => {},
  error: null,
  setError: () => {},
});

export function SaveStatusProvider({ readOnly, children }: { readOnly: boolean; children: ReactNode }) {
  const [state, setState] = useState<SaveState>(readOnly ? "readonly" : "saved");
  const [error, setError] = useState<string | null>(null);
  return <SaveStatusContext.Provider value={{ state: readOnly ? "readonly" : state, setState, error, setError }}>{children}</SaveStatusContext.Provider>;
}

export const useSaveStatus = () => useContext(SaveStatusContext);

/**
 * Debounced autosave of one wizard step. `body` is the step's PATCH payload;
 * whenever its JSON changes it is sent after `delay` ms. `flush()` sends any
 * pending change right away (used by Continue / Save & exit) and resolves
 * false when the save failed.
 */
export function useAutosave(path: string, body: object, { delay = 800, enabled = true } = {}) {
  const queryClient = useQueryClient();
  const { setState, setError } = useSaveStatus();
  const json = JSON.stringify(body);
  const lastSaved = useRef(json); // the step starts from saved data
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inflight = useRef<Promise<boolean> | null>(null);

  const send = useCallback(
    async (payload: string): Promise<boolean> => {
      if (payload === lastSaved.current) return true;
      setState("saving");
      try {
        const me = await api<Me>(path, { method: "PATCH", body: payload });
        lastSaved.current = payload;
        queryClient.setQueryData(["me"], me);
        setState("saved");
        setError(null);
        return true;
      } catch (e) {
        setState("error");
        setError(e instanceof Error ? e.message : "Couldn't save");
        return false;
      }
    },
    [path, queryClient, setState, setError],
  );

  useEffect(() => {
    if (!enabled || json === lastSaved.current) return;
    setState("pending");
    timer.current = setTimeout(() => {
      inflight.current = send(json);
    }, delay);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [json, delay, enabled, send, setState]);

  const flush = useCallback(async () => {
    if (!enabled) return true;
    if (timer.current) clearTimeout(timer.current);
    await inflight.current;
    return send(json);
  }, [enabled, json, send]);

  return { flush };
}
