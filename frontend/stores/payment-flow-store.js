"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export const usePaymentFlowStore = create(
  persist(
    (set) => ({
      draftOrder: {
        seller_id: "",
        seller_display_name: "",
        seller_contact: "",
        payout_destination: "avok_account",
        payout_reference: "",
        payout_account_name: "",
        payout_bank_name: "",
        product_name: "",
        product_description: "",
        product_price: "",
        delivery_method: "pickup",
        shipping_address: "",
        product_url: "",
        payment_source: "verified_account",
        merchant_name: "",
        return_url: "",
        cancel_url: ""
      },
      setDraftOrder: (draftOrder) => set({ draftOrder }),
      clearDraftOrder: () =>
        set({
          draftOrder: {
            seller_id: "",
            seller_display_name: "",
            seller_contact: "",
            payout_destination: "avok_account",
            payout_reference: "",
            payout_account_name: "",
            payout_bank_name: "",
            product_name: "",
            product_description: "",
            product_price: "",
            delivery_method: "pickup",
            shipping_address: "",
            product_url: "",
            payment_source: "verified_account",
            merchant_name: "",
            return_url: "",
            cancel_url: ""
          }
        })
    }),
    {
      name: "avok-payment-flow"
    }
  )
);
