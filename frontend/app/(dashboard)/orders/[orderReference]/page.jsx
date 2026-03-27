"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

export default function LegacyOrderDetailRedirectPage() {
  const router = useRouter();
  const params = useParams();

  useEffect(() => {
    const orderReference = encodeURIComponent(params.orderReference);
    router.replace(`/checkout/${orderReference}`);
  }, [params.orderReference, router]);

  return null;
}
