import { cva, type VariantProps } from "class-variance-authority";
import Link from "next/link";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-field px-5 font-bold whitespace-nowrap transition-colors disabled:pointer-events-none disabled:opacity-60",
  {
    variants: {
      variant: {
        primary: "bg-brand text-white hover:bg-brand-strong",
        outline: "border border-brand bg-surface text-brand hover:bg-brand-soft",
        neutral: "border border-line bg-surface text-ink hover:bg-page",
        ghost: "text-body hover:text-ink",
      },
      size: {
        sm: "h-11 text-[15px]",
        md: "h-12 text-[15px]",
        lg: "h-[50px] text-base",
        hero: "h-[52px] px-[26px] text-base",
      },
      block: { true: "w-full" },
    },
    defaultVariants: { variant: "primary", size: "lg" },
  },
);

type Variants = VariantProps<typeof buttonVariants>;

export function Button({ className, variant, size, block, ...props }: ComponentProps<"button"> & Variants) {
  return <button className={cn(buttonVariants({ variant, size, block }), className)} {...props} />;
}

export function ButtonLink({ className, variant, size, block, ...props }: ComponentProps<typeof Link> & Variants) {
  return <Link className={cn(buttonVariants({ variant, size, block }), className)} {...props} />;
}

/** Spinner shown inside a button while a request is in flight. */
export function Spinner({ className }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={cn("size-4 animate-spin rounded-full border-2 border-current border-t-transparent", className)}
    />
  );
}
