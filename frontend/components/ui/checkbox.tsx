import type { ComponentProps, ReactNode } from "react";

/** Square brand checkbox from the sign-up form (native input, styled). */
export function Checkbox({ children, ...props }: ComponentProps<"input"> & { children: ReactNode }) {
  return (
    <label className="flex cursor-pointer items-start gap-2 text-[13px] text-body">
      <span className="relative mt-px size-5 shrink-0">
        <input type="checkbox" className="peer absolute inset-0 size-5 cursor-pointer appearance-none rounded-md border border-line bg-surface checked:border-brand checked:bg-brand focus-visible:shadow-focus" {...props} />
        {/* eslint-disable-next-line @next/next/no-img-element -- fixed-size decorative SVG */}
        <img src="/icons/check-white.svg" alt="" width={12} height={12} className="pointer-events-none absolute inset-0 m-auto hidden size-3 peer-checked:block" />
      </span>
      <span>{children}</span>
    </label>
  );
}
