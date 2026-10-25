"use client";

import { useEffect, useState } from "react";

/** Counts from 0 to `to` (%) on mount; shows the final value right away for reduced motion. */
export function CountUp({ to, duration = 1200, className }: { to: number; duration?: number; className?: string }) {
  const [value, setValue] = useState(to);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      setValue(Math.round(to * (1 - Math.pow(1 - t, 3)))); // ease-out cubic
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    setValue(0);
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [to, duration]);

  return <span className={className}>{value}%</span>;
}
