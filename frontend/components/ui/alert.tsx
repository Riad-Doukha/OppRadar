import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

const tones = {
  danger: { box: "border border-danger-line bg-danger-soft text-danger font-medium", icon: "/icons/alert-circle-red.svg" },
  info: { box: "bg-page text-body", icon: "/icons/info-purple.svg" },
};

export function Alert({ tone = "danger", children, className }: { tone?: keyof typeof tones; children: ReactNode; className?: string }) {
  const t = tones[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("flex items-start gap-2.5 rounded-field px-3.5 py-3 text-sm", t.box, className)}>
      {/* eslint-disable-next-line @next/next/no-img-element -- fixed-size decorative SVG */}
      <img src={t.icon} alt="" width={18} height={18} className="mt-px size-[18px] shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}
