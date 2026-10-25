import Image from "next/image";
import { useTranslations } from "next-intl";

import { cn } from "@/lib/utils";

/** Yellow "PREVIEW — coming soon" pill used on every Premium screen. */
export function PreviewPill({ className, children }: { className?: string; children?: React.ReactNode }) {
  const t = useTranslations("premium");
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full bg-signal px-3.5 py-1.5 text-xs font-bold text-on-signal", className)}>
      <Image src="/icons/sparkle-dark.svg" alt="" width={13} height={13} />
      {children ?? t("pill")}
    </span>
  );
}

/** The plain-language notice: nothing is charged, features aren't live yet. */
export function ComingSoonNotice({ className }: { className?: string }) {
  const t = useTranslations("premium");
  return (
    <div role="note" className={cn("rounded-field border border-warning-line bg-warning-tint px-4 py-3 text-sm text-ink", className)}>
      {t.rich("notice", { strong: (c) => <strong>{c}</strong> })}
    </div>
  );
}
