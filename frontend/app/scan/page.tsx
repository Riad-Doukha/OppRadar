
import { FirstScan } from "@/components/dashboard/first-scan";
import { titled } from "@/i18n/metadata";

export const generateMetadata = titled("scan");

export default function ScanPage() {
  return <FirstScan />;
}
