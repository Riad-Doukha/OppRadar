"use client";

import { useRef, type PointerEvent, type ReactNode } from "react";

/**
 * Tracks the mouse over its box and exposes the position as CSS variables
 * --px / --py in [-1, 1] (0 = centre). Children use them in transforms
 * (see .parallax-* in globals.css). Mouse only; nothing for touch or
 * reduced motion.
 */
export function RadarParallax({ className, children }: { className?: string; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const frame = useRef(0);

  function set(x: number, y: number) {
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      ref.current?.style.setProperty("--px", x.toFixed(3));
      ref.current?.style.setProperty("--py", y.toFixed(3));
    });
  }

  function onMove(e: PointerEvent<HTMLDivElement>) {
    if (e.pointerType !== "mouse" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const box = e.currentTarget.getBoundingClientRect();
    set(((e.clientX - box.left) / box.width) * 2 - 1, ((e.clientY - box.top) / box.height) * 2 - 1);
  }

  return (
    <div ref={ref} className={className} onPointerMove={onMove} onPointerLeave={() => set(0, 0)} aria-hidden>
      {children}
    </div>
  );
}
