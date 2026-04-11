"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

const EMPTY_CART_ITEM = {
  item_name: "",
  item_description: "",
  quantity: 1,
  unit_price: "",
  product_url: "",
};

const EMPTY_DRAFT_ORDER = {
  seller_id: "",
  seller_display_name: "",
  seller_contact: "",
  payout_destination: "avok_account",
  payout_reference: "",
  payout_account_name: "",
  payout_bank_name: "",
  merchant_intent_reference: "",
  product_name: "",
  product_description: "",
  product_price: "",
  items: [],
  delivery_method: "pickup",
  shipping_address: "",
  product_url: "",
  payment_source: "verified_account",
  merchant_name: "",
  return_url: "",
  cancel_url: "",
};

export const usePaymentFlowStore = create(
  persist(
    (set, get) => ({
      draftOrder: EMPTY_DRAFT_ORDER,
      isMerchantVerified: false,

      setDraftOrder: (draftOrder) =>
        set((state) => {
          const newItems = Array.isArray(draftOrder?.items) ? draftOrder.items : state.draftOrder.items;
          const cappedItems = newItems.slice(0, 50);
          return {
            draftOrder: {
              ...state.draftOrder,
              ...draftOrder,
              items: cappedItems,
            },
          };
        }),

      setMerchantVerified: (value) => set({ isMerchantVerified: !!value }),

      clearDraftOrder: () => set({ draftOrder: { ...EMPTY_DRAFT_ORDER }, isMerchantVerified: false }),

      addItem: () =>
        set((state) => ({
          draftOrder: {
            ...state.draftOrder,
            items: [...state.draftOrder.items, { ...EMPTY_CART_ITEM }],
          },
        })),

      updateItem: (index, field, value) =>
        set((state) => {
          const items = [...state.draftOrder.items];
          if (items[index]) {
            items[index] = { ...items[index], [field]: value };
          }
          return { draftOrder: { ...state.draftOrder, items } };
        }),

      removeItem: (index) =>
        set((state) => ({
          draftOrder: {
            ...state.draftOrder,
            items: state.draftOrder.items.filter((_, i) => i !== index),
          },
        })),

      getCartTotal: () => {
        const { items, product_price } = get().draftOrder;
        if (items.length > 0) {
          return items.reduce((sum, item) => {
            const qty = parseInt(item.quantity, 10) || 1;
            const price = parseFloat(item.unit_price) || 0;
            return sum + qty * price;
          }, 0);
        }
        return parseFloat(product_price) || 0;
      },
    }),
    {
      name: "avok-payment-flow",
    }
  )
);
