"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export default function LegacyCreateOrderRedirectPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const queryString = searchParams.toString();
    router.replace(queryString ? `/checkout/new?${queryString}` : "/checkout/new");
  }, [router, searchParams]);

  return null;
}
