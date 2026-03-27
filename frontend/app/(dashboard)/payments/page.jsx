"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { usePaymentFlowStore } from "@/stores/payment-flow-store";

export default function PaymentsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setDraftOrder, clearDraftOrder } = usePaymentFlowStore();

  useEffect(() => {
    const seededOrder = {
      seller_id: searchParams.get("seller_id") || "",
      seller_display_name: searchParams.get("seller_display_name") || "",
      seller_contact: searchParams.get("seller_contact") || "",
      payout_destination: searchParams.get("payout_destination") || "avok_account",
      payout_reference: searchParams.get("payout_reference") || "",
      payout_account_name: searchParams.get("payout_account_name") || "",
      payout_bank_name: searchParams.get("payout_bank_name") || "",
      product_name: searchParams.get("product_name") || "",
      product_description: searchParams.get("product_description") || "",
      product_price: searchParams.get("amount") || searchParams.get("product_price") || "",
      delivery_method: searchParams.get("delivery_method") || "pickup",
      shipping_address: searchParams.get("shipping_address") || "",
      product_url: searchParams.get("product_url") || "",
      payment_source: searchParams.get("funding_source") || searchParams.get("payment_source") || "verified_account",
      merchant_name: searchParams.get("merchant_name") || "",
      return_url: searchParams.get("return_url") || "",
      cancel_url: searchParams.get("cancel_url") || ""
    };

    const hasEmbeddedPayload = Object.values(seededOrder).some((value) => value);

    if (!hasEmbeddedPayload) {
      clearDraftOrder();
      router.replace("/checkout/new");
      return;
    }

    setDraftOrder(seededOrder);
    router.replace("/checkout/new?embedded=1");
  }, [clearDraftOrder, router, searchParams, setDraftOrder]);

  return (
    <div className="card rounded-[28px] p-6">
      <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Pay with Avok</p>
      <h2 className="mt-3 text-3xl font-black">Preparing secure checkout session</h2>
      <p className="mt-3 max-w-2xl text-sm leading-7 text-stone-600">
        Avok is loading the product and payout details sent from the external website, then moving you into checkout so you do not need to enter them again.
      </p>
    </div>
  );
}
