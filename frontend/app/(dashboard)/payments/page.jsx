"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";

import { api } from "@/lib/api";
import { usePaymentFlowStore } from "@/stores/payment-flow-store";

export default function PaymentsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const intentReference = searchParams.get("intent");
  const { setDraftOrder, clearDraftOrder } = usePaymentFlowStore();

  const intentQuery = useQuery({
    queryKey: ["merchant-intent", intentReference],
    enabled: Boolean(intentReference),
    queryFn: async () => {
      const response = await api.get(`/payments/embed/intents/${intentReference}`);
      return response.data;
    }
  });

  useEffect(() => {
    if (!intentReference) {
      clearDraftOrder();
      return;
    }

    if (!intentQuery.data) {
      return;
    }

    const intent = intentQuery.data;
    setDraftOrder({
      ...intent,
      isMerchantVerified: true,
      merchant_intent_reference: intent.intent_reference
    });
    router.replace(`/checkout/new?embedded=1&intent=${intent.intent_reference}`);
  }, [clearDraftOrder, intentQuery.data, intentReference, router, setDraftOrder]);

  if (!intentReference) {
    return (
      <div className="card rounded-[28px] p-6">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Pay with Avok</p>
        <h2 className="mt-3 text-3xl font-black">Missing secure checkout intent</h2>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-stone-600">
          This embedded checkout link is missing the server-issued intent reference Avok needs to trust the merchant payload.
        </p>
      </div>
    );
  }

  if (intentQuery.isError) {
    return (
      <div className="card rounded-[28px] p-6">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Pay with Avok</p>
        <h2 className="mt-3 text-3xl font-black">Secure checkout could not be prepared</h2>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-stone-600">{intentQuery.error.message}</p>
      </div>
    );
  }

  return (
    <div className="card rounded-[28px] p-6">
      <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Pay with Avok</p>
      <h2 className="mt-3 text-3xl font-black">Preparing secure checkout session</h2>
      <p className="mt-3 max-w-2xl text-sm leading-7 text-stone-600">
        Avok is loading the merchant-signed checkout intent from the server, then moving you into checkout with trusted product and payout details.
      </p>
    </div>
  );
}
