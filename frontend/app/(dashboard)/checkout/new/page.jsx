"use client";

import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { calculateCappedFee } from "@/lib/fees";
import { usePaymentFlowStore } from "@/stores/payment-flow-store";
import { useAuthStore } from "@/stores/auth-store";

const deliveryMethods = [
  { value: "pickup", label: "Pickup" },
  { value: "delivery", label: "Delivery" }
];

export default function CreateCheckoutPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { draftOrder, setDraftOrder, clearDraftOrder } = usePaymentFlowStore();
  const accessToken = useAuthStore((state) => state.accessToken);
  const setSession = useAuthStore((state) => state.setSession);
  const [showManualFields, setShowManualFields] = useState(false);
  const [guest, setGuest] = useState({
    guest_full_name: "",
    guest_phone_number: "",
    guest_email: "",
  });
  const [form, setForm] = useState({
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
  });

  const isEmbeddedCheckout = searchParams.get("embedded") === "1";

  useEffect(() => {
    const seeded = {
      seller_id: searchParams.get("seller_id") || draftOrder.seller_id || "",
      seller_display_name: searchParams.get("seller_display_name") || draftOrder.seller_display_name || "",
      seller_contact: searchParams.get("seller_contact") || draftOrder.seller_contact || "",
      payout_destination: searchParams.get("payout_destination") || draftOrder.payout_destination || "avok_account",
      payout_reference: searchParams.get("payout_reference") || draftOrder.payout_reference || "",
      payout_account_name: searchParams.get("payout_account_name") || draftOrder.payout_account_name || "",
      payout_bank_name: searchParams.get("payout_bank_name") || draftOrder.payout_bank_name || "",
      product_name: searchParams.get("product_name") || draftOrder.product_name || "",
      product_description: searchParams.get("product_description") || draftOrder.product_description || "",
      product_price: searchParams.get("product_price") || draftOrder.product_price || "",
      delivery_method: searchParams.get("delivery_method") || draftOrder.delivery_method || "pickup",
      shipping_address: searchParams.get("shipping_address") || draftOrder.shipping_address || "",
      product_url: searchParams.get("product_url") || draftOrder.product_url || "",
      payment_source: searchParams.get("payment_source") || draftOrder.payment_source || "verified_account",
      merchant_name: searchParams.get("merchant_name") || draftOrder.merchant_name || "",
      return_url: searchParams.get("return_url") || draftOrder.return_url || "",
      cancel_url: searchParams.get("cancel_url") || draftOrder.cancel_url || ""
    };
    setForm(seeded);
  }, [draftOrder, searchParams]);

  const createOrderMutation = useMutation({
    mutationFn: async (payload) => {
      const requestPayload = {
        ...payload,
        recipient_id: payload.seller_id ? Number(payload.seller_id) : null,
        recipient_display_name: payload.seller_display_name,
        recipient_contact: payload.seller_contact,
        product_price: Number(payload.product_price),
        auto_import_product_details: Boolean(payload.product_url)
      };
      delete requestPayload.seller_id;
      delete requestPayload.seller_display_name;
      delete requestPayload.seller_contact;

      const response = accessToken
        ? await api.post("/checkout/sessions/", requestPayload)
        : await api.post("/checkout/sessions/guest", {
            ...requestPayload,
            ...guest,
            merchant_name: payload.merchant_name || undefined,
            return_url: payload.return_url || undefined,
            cancel_url: payload.cancel_url || undefined,
          });
      return response.data;
    },
    onSuccess: (data) => {
      if (data?.access_token) {
        setSession({
          accessToken: data.access_token,
          user: {
            id: data.guest_user_id,
            phone_number: guest.guest_phone_number,
            full_name: guest.guest_full_name,
            email: guest.guest_email || null,
            role: "buyer"
          }
        });
      }
      clearDraftOrder();
      router.push(`/checkout/${data.session_reference || data.order_reference}`);
    }
  });

  const productPrice = Number(form.product_price || 0);
  const depositFee = calculateCappedFee(productPrice);
  const hasImportedSeed =
    isEmbeddedCheckout &&
    Boolean(
      form.product_url ||
        form.product_name ||
        form.product_description ||
        form.product_price ||
        form.seller_display_name ||
        form.payout_reference
    );

  return (
    <div className="space-y-5">
      <section className="card rounded-[28px] p-6">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">
          {isEmbeddedCheckout ? "Pay with Avok" : "Create checkout session"}
        </p>
        <h2 className="mt-3 text-3xl font-black">
          {isEmbeddedCheckout
            ? "Review the imported product and payout details before Avok starts secure checkout."
            : "Create a checkout session and see the escrow math before payment starts."}
        </h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-stone-600">
          {isEmbeddedCheckout
            ? "The external website should send the product link, amount, and payout details into Avok automatically. You can still add or correct information before continuing."
            : "This screen is built for practical testing. Enter the payout recipient, product, and price, then the app shows what the payer funds now and what the recipient receives after escrow release."}
        </p>
      </section>

      {!accessToken ? (
        <section className="card rounded-[28px] p-6">
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Guest checkout</p>
          <h3 className="mt-3 text-2xl font-black">Continue without creating a full Avok account first</h3>
          <p className="mt-2 max-w-3xl text-sm leading-7 text-stone-600">
            Avok will create a temporary payer session so you can fund escrow, track delivery, and open a dispute if needed. You can still create a full verified account later.
          </p>
          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            <input
              className="field"
              value={guest.guest_full_name}
              onChange={(event) => setGuest((prev) => ({ ...prev, guest_full_name: event.target.value }))}
              placeholder="Your full name"
            />
            <input
              className="field"
              value={guest.guest_phone_number}
              onChange={(event) => setGuest((prev) => ({ ...prev, guest_phone_number: event.target.value }))}
              placeholder="0241111111"
            />
            <input
              className="field"
              value={guest.guest_email}
              onChange={(event) => setGuest((prev) => ({ ...prev, guest_email: event.target.value }))}
              placeholder="Optional email"
            />
          </div>
        </section>
      ) : null}

      {form.merchant_name || form.return_url || form.cancel_url ? (
        <section className="card rounded-[28px] p-6">
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Merchant context</p>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <div className="rounded-[22px] bg-stone-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500">Merchant</p>
              <p className="mt-2 text-sm font-bold text-stone-900">{form.merchant_name || "Embedded merchant"}</p>
            </div>
            <div className="rounded-[22px] bg-stone-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500">Return URL</p>
              <p className="mt-2 truncate text-sm text-stone-700">{form.return_url || "Not supplied"}</p>
            </div>
            <div className="rounded-[22px] bg-stone-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500">Cancel URL</p>
              <p className="mt-2 truncate text-sm text-stone-700">{form.cancel_url || "Not supplied"}</p>
            </div>
          </div>
        </section>
      ) : null}

      {hasImportedSeed ? (
        <section className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
          <div className="card rounded-[28px] p-6">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Imported from merchant</p>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="rounded-[22px] bg-stone-50 p-4 sm:col-span-2">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500">Product</p>
                <p className="mt-2 text-lg font-bold text-stone-900">{form.product_name || "Product details will be imported from the link"}</p>
                <p className="mt-2 text-sm leading-6 text-stone-600">{form.product_description || "Avok will try to fetch the product title, description, images, and videos automatically."}</p>
                {form.product_url ? (
                  <a href={form.product_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex text-sm font-semibold text-emerald-800">
                    Open source product link
                  </a>
                ) : null}
              </div>
              <div className="rounded-[22px] bg-stone-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500">Amount</p>
                <p className="mt-2 text-lg font-bold text-stone-900">GHS {productPrice.toLocaleString()}</p>
              </div>
              <div className="rounded-[22px] bg-stone-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500">Payout recipient</p>
                <p className="mt-2 text-lg font-bold text-stone-900">{form.seller_display_name || form.payout_account_name || "Recipient details imported"}</p>
                <p className="mt-2 text-sm text-stone-600">{form.payout_reference || "Avok will release to the imported payout destination."}</p>
              </div>
            </div>
            <button
              type="button"
              className="mt-5 text-sm font-semibold text-emerald-800"
              onClick={() => setShowManualFields((prev) => !prev)}
            >
              {showManualFields ? "Hide manual adjustments" : "Add or correct details manually"}
            </button>
          </div>

          <section className="card rounded-[28px] bg-stone-900 p-6 text-white">
            <p className="text-sm uppercase tracking-[0.18em] text-stone-300">Embedded checkout flow</p>
            <div className="mt-5 space-y-4">
              <div className="rounded-[22px] bg-white/10 p-4">
                <p className="text-sm text-stone-300">What Avok imported</p>
                <p className="mt-1 text-sm leading-6 text-stone-100">
                  Product details should come from the external website or product link first, so the payer is not starting from a blank form.
                </p>
              </div>
              <div className="rounded-[22px] bg-white/10 p-4">
                <p className="text-sm text-stone-300">What the user can still do</p>
                <p className="mt-1 text-sm leading-6 text-stone-100">
                  Review the imported data, add missing delivery notes, and correct payout or product details if something looks wrong.
                </p>
              </div>
              <div className="rounded-[22px] bg-emerald-900/70 p-4 text-sm leading-6 text-emerald-50">
                Avok should feel like a secure payment layer sitting on top of another website, not a separate marketplace form.
              </div>
            </div>
          </section>
        </section>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setDraftOrder(form);
            createOrderMutation.mutate(form);
          }}
          className="card rounded-[28px] p-6"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            {!isEmbeddedCheckout || showManualFields ? (
              <>
                <div>
                  <label className="mb-2 block text-sm font-semibold text-stone-700">Recipient user ID</label>
                  <input className="field" value={form.seller_id} onChange={(event) => setForm((prev) => ({ ...prev, seller_id: event.target.value }))} placeholder="2" />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-semibold text-stone-700">Payout recipient name</label>
                  <input className="field" value={form.seller_display_name} onChange={(event) => setForm((prev) => ({ ...prev, seller_display_name: event.target.value }))} placeholder="Shanghai Machine Store" />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-semibold text-stone-700">Recipient contact</label>
                  <input className="field" value={form.seller_contact} onChange={(event) => setForm((prev) => ({ ...prev, seller_contact: event.target.value }))} placeholder="Phone or email" />
                </div>
              </>
            ) : null}
            <div>
              <label className="mb-2 block text-sm font-semibold text-stone-700">Payout destination</label>
              <select className="field" value={form.payout_destination} onChange={(event) => setForm((prev) => ({ ...prev, payout_destination: event.target.value }))}>
                <option value="avok_account">Avok verified account</option>
                <option value="momo">Mobile money</option>
                <option value="bank">Bank account</option>
              </select>
            </div>
            <div>
              <label className="mb-2 block text-sm font-semibold text-stone-700">Payout reference</label>
              <input className="field" value={form.payout_reference} onChange={(event) => setForm((prev) => ({ ...prev, payout_reference: event.target.value }))} placeholder="MoMo number or bank account number" />
            </div>
            <div>
              <label className="mb-2 block text-sm font-semibold text-stone-700">Payout account name</label>
              <input className="field" value={form.payout_account_name} onChange={(event) => setForm((prev) => ({ ...prev, payout_account_name: event.target.value }))} placeholder="Recipient account name" />
            </div>
            <div>
              <label className="mb-2 block text-sm font-semibold text-stone-700">Bank name</label>
              <input className="field" value={form.payout_bank_name} onChange={(event) => setForm((prev) => ({ ...prev, payout_bank_name: event.target.value }))} placeholder="Optional for bank payout" />
            </div>
            <div>
              <label className="mb-2 block text-sm font-semibold text-stone-700">Product price (GHS)</label>
              <input className="field" value={form.product_price} onChange={(event) => setForm((prev) => ({ ...prev, product_price: event.target.value }))} placeholder="4200" />
            </div>
            <div className="sm:col-span-2">
              <label className="mb-2 block text-sm font-semibold text-stone-700">Product link</label>
              <input className="field" value={form.product_url} onChange={(event) => setForm((prev) => ({ ...prev, product_url: event.target.value }))} placeholder="https://example.com/product" />
            </div>
            <div className="sm:col-span-2">
              <label className="mb-2 block text-sm font-semibold text-stone-700">Product name</label>
              <input className="field" value={form.product_name} onChange={(event) => setForm((prev) => ({ ...prev, product_name: event.target.value }))} placeholder="Imported or corrected product name" />
              <p className="mt-2 text-xs text-stone-500">If you paste a product link, Avok can try to import the title, description, images, and videos automatically.</p>
            </div>
            <div className="sm:col-span-2">
              <label className="mb-2 block text-sm font-semibold text-stone-700">Product description</label>
              <textarea rows={4} className="field" value={form.product_description} onChange={(event) => setForm((prev) => ({ ...prev, product_description: event.target.value }))} placeholder="Add anything the imported listing missed, such as condition or delivery notes." />
            </div>
            <div>
              <label className="mb-2 block text-sm font-semibold text-stone-700">Delivery method</label>
              <select className="field" value={form.delivery_method} onChange={(event) => setForm((prev) => ({ ...prev, delivery_method: event.target.value }))}>
                {deliveryMethods.map((method) => (
                  <option key={method.value} value={method.value}>
                    {method.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-2 block text-sm font-semibold text-stone-700">Payment source</label>
              <select className="field" value={form.payment_source} onChange={(event) => setForm((prev) => ({ ...prev, payment_source: event.target.value }))}>
                <option value="verified_account">Verified Avok account</option>
                <option value="momo">Mobile money directly into escrow</option>
                <option value="bank">Bank transfer directly into escrow</option>
              </select>
            </div>
            <div>
              <label className="mb-2 block text-sm font-semibold text-stone-700">Shipping address</label>
              <input className="field" value={form.shipping_address} onChange={(event) => setForm((prev) => ({ ...prev, shipping_address: event.target.value }))} placeholder="East Legon, Accra" />
            </div>
          </div>

          <button type="submit" className="btn-primary mt-5 w-full">
            {createOrderMutation.isPending ? "Creating session..." : !accessToken ? "Continue as guest payer" : isEmbeddedCheckout ? "Continue secure checkout" : "Create checkout session"}
          </button>

          {createOrderMutation.isSuccess ? (
            <div className="mt-4 rounded-[22px] bg-emerald-50 p-4 text-sm text-emerald-800">
              <p className="font-semibold">Checkout session created successfully.</p>
              <p className="mt-1">Reference: {createOrderMutation.data.order_reference}</p>
              <Link href={`/checkout/${createOrderMutation.data.order_reference}`} className="mt-3 inline-flex font-bold text-emerald-900">
                Open checkout session
              </Link>
            </div>
          ) : null}

          {createOrderMutation.isError ? <p className="mt-4 rounded-2xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">{createOrderMutation.error.message}</p> : null}
        </form>

        <section className="card rounded-[28px] bg-stone-900 p-6 text-white">
          <p className="text-sm uppercase tracking-[0.18em] text-stone-300">Escrow preview</p>
          <div className="mt-5 space-y-4">
            <div className="rounded-[22px] bg-white/10 p-4">
              <p className="text-sm text-stone-300">If payer funds from MoMo or bank</p>
              <p className="mt-1 text-3xl font-black">GHS {depositFee.toFixed(2)}</p>
              <p className="mt-2 text-sm text-stone-200">Entry fee is 1% capped at GHS 30 before money reaches the verified Avok account.</p>
            </div>
            <div className="rounded-[22px] bg-white/10 p-4">
              <p className="text-sm text-stone-300">If paid from verified Avok balance</p>
              <p className="mt-1 text-3xl font-black">No purchase fee</p>
              <p className="mt-2 text-sm text-stone-200">Using money already inside a verified Avok account for purchases should be free.</p>
            </div>
            <div className="rounded-[22px] bg-emerald-900/70 p-4 text-sm leading-6 text-emerald-50">
              Avok should autofill this checkout session when the user proceeds from the Pay with Avok flow, then hold the money in escrow until delivery or dispute resolution.
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
