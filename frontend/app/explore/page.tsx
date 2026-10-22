import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { Suspense } from "react";

import { PublicHeader } from "@/components/brand/public-header";
import { ExplorePage } from "@/components/explore/explore-page";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("explore"))("title") };
}

export default function Page() {
  return (
    <div className="min-h-dvh bg-page">
      <PublicHeader active="explore" />
      <Suspense>
        <ExplorePage />
      </Suspense>
    </div>
  );
}
