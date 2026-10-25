"use client";

import { useCallback, useEffect, useState } from "react";

/** Seconds left before an action (e.g. "Resend email") is allowed again. */
export function useCountdown(initialSeconds: number) {
  const [left, setLeft] = useState(initialSeconds);

  useEffect(() => {
    if (left <= 0) return;
    const t = setTimeout(() => setLeft((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [left]);

  const restart = useCallback((seconds = initialSeconds) => setLeft(seconds), [initialSeconds]);
  const label = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
  return { left, done: left <= 0, label, restart };
}
