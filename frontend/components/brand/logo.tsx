import Image from "next/image";
import Link from "next/link";
import { useTranslations } from "next-intl";

/** OppRadar wordmark (118×27 in the design). Purple on light, yellow on the dark footer. */
export function Logo({ tone = "purple", href = "/" }: { tone?: "purple" | "yellow"; href?: string | null }) {
  const t = useTranslations("common");
  const img = <Image src={`/brand/logo-${tone}.svg`} alt="OppRadar" width={118} height={27} priority />;
  return href ? (
    <Link href={href} className="inline-flex shrink-0" aria-label={t("home")}>
      {img}
    </Link>
  ) : (
    img
  );
}
