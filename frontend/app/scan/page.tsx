import type { Metadata } from "next";

import { FirstScan } from "@/components/dashboard/first-scan";

export const metadata: Metadata = { title: "Starting your agent" };

export default function ScanPage() {
  return <FirstScan />;
}
