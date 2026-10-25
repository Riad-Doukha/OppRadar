"use client";

import { useCallback, useSyncExternalStore } from "react";

import { THEME_KEY as KEY } from "./theme-script";

export type Theme = "system" | "light" | "dark";

export const THEMES: { value: Theme; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

const listeners = new Set<() => void>();

function read(): Theme {
  try {
    const t = localStorage.getItem(KEY);
    return t === "light" || t === "dark" ? t : "system";
  } catch {
    return "system";
  }
}

function apply(theme: Theme) {
  const dark = theme === "dark" || (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  // "System" follows the OS live; other tabs follow a change made here.
  const media = matchMedia("(prefers-color-scheme: dark)");
  const onMedia = () => apply(read());
  const onStorage = (e: StorageEvent) => {
    if (e.key !== KEY) return;
    apply(read());
    onChange();
  };
  media.addEventListener("change", onMedia);
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(onChange);
    media.removeEventListener("change", onMedia);
    window.removeEventListener("storage", onStorage);
  };
}

/** The chosen theme (per device) and a setter that applies it immediately. */
export function useTheme(): [Theme, (t: Theme) => void] {
  const theme = useSyncExternalStore(subscribe, read, () => "system" as Theme);
  const setTheme = useCallback((t: Theme) => {
    try {
      if (t === "system") localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, t);
    } catch {
      // Storage blocked: still switch for this page view.
    }
    apply(t);
    listeners.forEach((l) => l());
  }, []);
  return [theme, setTheme];
}
