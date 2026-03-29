"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import EscrowStatusBadge from "@/components/EscrowStatusBadge";
import OTPInput from "@/components/OTPInput";
import { api } from "@/lib/api";
import { calculateCappedFee } from "@/lib/fees";

function formatMoney(value) {
  return new Intl.NumberFormat("en-GH", {
    style: "currency",
    currency: "GHS",
    maximumFractionDigits: 2
  }).format(Number(value || 0));
}

function describeMoneyHolder(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized === "completed" || normalized === "released") {
    return "Released to recipient";
  }
  if (normalized === "refunded") {
    return "Returned to payer";
  }
  return "Avok escrow";
}

function formatDestination(value) {
  if (!value) {
    return "Avok verified account";
  }

  if (value === "verified_account" || value === "avok_account") {
    return "Avok verified account";
  }

  return String(value).replaceAll("_", " ");
}

function formatViewerRole(role) {
  if (role === "recipient") {
    return "recipient";
  }
  if (role === "admin") {
    return "admin monitor";
  }
  return "payer";
}

export default function CheckoutDetailPage() {
  const queryClient = useQueryClient();
  const params = useParams();
  const [paymentForm, setPaymentForm] = useState({
    momo_provider: "mtn",
    momo_number: "",
    funding_source: "verified_account",
    payout_destination: "verified_account"
  });
  const [otp, setOtp] = useState("");
  const orderReference = decodeURIComponent(params.sessionReference);

  const orderQuery = useQuery({
    queryKey: ["order", orderReference],
    queryFn: async () => {
      const response = await api.get(`/checkout/sessions/${orderReference}`);
      return response.data;
    }
  });

  const paymentMutation = useMutation({
    mutationFn: async (payload) => {
      const response = await api.post(`/checkout/sessions/${orderReference}/fund`, payload);
      return response.data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["order", orderReference] }),
        queryClient.invalidateQueries({ queryKey: ["wallet-balance"] }),
        queryClient.invalidateQueries({ queryKey: ["wallet-transactions"] })
      ]);
    },
  });

  const sandboxSuccessMutation = useMutation({
    mutationFn: async (reference) => {
      const response = await api.post(`/payments/sandbox/${reference}/success`);
      return response.data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["order", orderReference] }),
        queryClient.invalidateQueries({ queryKey: ["wallet-balance"] }),
        queryClient.invalidateQueries({ queryKey: ["wallet-transactions"] })
      ]);
    },
  });

  const sandboxFailMutation = useMutation({
    mutationFn: async (reference) => {
      const response = await api.post(`/payments/sandbox/${reference}/fail`);
      return response.data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["order", orderReference] });
    },
  });

  const payerConfirmMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/checkout/sessions/${orderReference}/confirm`);
      return response.data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["order", orderReference] }),
        queryClient.invalidateQueries({ queryKey: ["wallet-balance"] }),
        queryClient.invalidateQueries({ queryKey: ["wallet-transactions"] })
      ]);
    },
  });

  const recipientOtpMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/orders/${orderReference}/delivery/otp`);
      return response.data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["order", orderReference] });
    },
  });

  const recipientConfirmMutation = useMutation({
    mutationFn: async (enteredOtp) => {
      const response = await api.post(`/orders/${orderReference}/delivery/confirm`, {
        order_reference: orderReference,
        otp: enteredOtp
      });
      return response.data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["order", orderReference] }),
        queryClient.invalidateQueries({ queryKey: ["wallet-balance"] }),
        queryClient.invalidateQueries({ queryKey: ["wallet-transactions"] })
      ]);
    },
  });

  const order = orderQuery.data;
  if (!order && !orderQuery.isLoading) {
    return (
      <div className="card rounded-[28px] p-6">
        <h2 className="text-2xl font-black">Checkout session not found</h2>
        <p className="mt-2 text-sm text-stone-600">Use checkout to make a new session and test it from scratch.</p>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="card rounded-[28px] p-6">
        <h2 className="text-2xl font-black">Loading checkout session...</h2>
      </div>
    );
  }
  const entryFee = paymentForm.funding_source === "verified_account" ? 0 : calculateCappedFee(order.product_price);
  const releaseFee = paymentForm.payout_destination === "verified_account" ? 0 : calculateCappedFee(order.product_price);
  const recipientNet = Number(order.product_price || 0) - releaseFee;
  const heldAmount = Number(order.product_price || 0) + entryFee;
  const payoutDestination = order.payout_destination || paymentForm.payout_destination;
  const actorLabel = formatViewerRole(order.viewer_role);
  const canFund = Boolean(order.can_fund);
  const canConfirmDelivery = Boolean(order.can_confirm_delivery);
  const canGenerateDeliveryOtp = Boolean(order.can_generate_delivery_otp);
  const canSubmitDeliveryOtp = Boolean(order.can_submit_delivery_otp);
  const isReadOnlyMonitor = Boolean(order.is_read_only_monitor);

  const timeline = useMemo(
    () => [
      {
        title: "1. Checkout session is created",
        body: "Checkout details are locked in and Avok prepares the escrow payment path."
      },
      {
        title: "2. Payer funds escrow",
        body: "The payer funds the product price and any entry fee. Avok holds the money securely."
      },
      {
        title: "3. Recipient prepares delivery and shares OTP",
        body: "The payout recipient prepares delivery and generates an OTP for proof of handover."
      },
      {
        title: "4. Payer confirms delivery or recipient submits OTP",
        body: "Once confirmed, escrow is released."
      },
      {
        title: "5. Recipient receives funds",
        body: "The recipient gets the product value, with release fees only when funds go directly to bank or MoMo."
      }
    ],
    []
  );

  return (
    <div className="space-y-5">
      <section className="card rounded-[28px] p-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">{order.session_reference || order.order_reference}</p>
            <h2 className="mt-3 text-3xl font-black">{order.product_name}</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-stone-600">{order.product_description || "Escrow-backed payment session."}</p>
          </div>
          <EscrowStatusBadge status={order.escrow_status} />
        </div>
        <div className="mt-5 rounded-[22px] bg-stone-50 p-4 text-sm leading-6 text-stone-700">
          <span className="font-semibold">Your view:</span> You are currently monitoring this checkout session as the {actorLabel}. Both sides can watch the funds move, but Avok only shows actions that match your role in this transaction.
        </div>
        {isReadOnlyMonitor ? (
          <div className="mt-4 rounded-[22px] bg-amber-50 p-4 text-sm leading-6 text-amber-900">
            This is a read-only monitoring view right now. You can track escrow status, held funds, and delivery progress here, but there is no action required from your side at the current stage.
          </div>
        ) : null}
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="card rounded-[24px] p-5">
          <p className="text-sm text-stone-500">Product price</p>
          <p className="mt-2 text-2xl font-black">{formatMoney(order.product_price)}</p>
        </div>
        <div className="card rounded-[24px] p-5">
          <p className="text-sm text-stone-500">Entry fee</p>
          <p className="mt-2 text-2xl font-black">{formatMoney(order.platform_fee)}</p>
        </div>
        <div className="card rounded-[24px] p-5">
          <p className="text-sm text-stone-500">Release fee on current payout path</p>
          <p className="mt-2 text-2xl font-black">{formatMoney(releaseFee)}</p>
        </div>
        <div className="card rounded-[24px] p-5">
          <p className="text-sm text-stone-500">Who holds the money now</p>
          <p className="mt-2 text-2xl font-black">{describeMoneyHolder(order.escrow_status)}</p>
        </div>
      </section>

      <section className="card rounded-[24px] p-5">
        <div className="grid gap-3 md:grid-cols-3">
          <div>
            <p className="text-sm text-stone-500">Payout recipient</p>
            <p className="mt-1 font-bold">{order.recipient_display_name || order.seller_display_name || "External recipient"}</p>
          </div>
          <div>
            <p className="text-sm text-stone-500">Payout route</p>
            <p className="mt-1 font-bold capitalize">{formatDestination(payoutDestination)}</p>
          </div>
          <div>
            <p className="text-sm text-stone-500">Product source</p>
            <p className="mt-1 font-bold">{order.source_site_name || "Manual entry"}</p>
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <section className="space-y-4">
          <div className="card rounded-[28px] p-6">
            <h3 className="text-xl font-bold">Escrow breakdown</h3>
            <div className="mt-5 space-y-3">
              <div className="flex items-center justify-between rounded-[20px] bg-stone-50 px-4 py-3">
                <span className="text-sm text-stone-600">Entry charge into escrow</span>
                <span className="font-bold">{formatMoney(entryFee)}</span>
              </div>
              <div className="flex items-center justify-between rounded-[20px] bg-stone-50 px-4 py-3">
                <span className="text-sm text-stone-600">Held by Avok escrow</span>
                <span className="font-bold">{formatMoney(heldAmount)}</span>
              </div>
              <div className="flex items-center justify-between rounded-[20px] bg-stone-50 px-4 py-3">
                <span className="text-sm text-stone-600">Recipient gets after release</span>
                <span className="font-bold">{formatMoney(recipientNet)}</span>
              </div>
              <div className="flex items-center justify-between rounded-[20px] bg-stone-50 px-4 py-3">
                <span className="text-sm text-stone-600">Release destination</span>
                <span className="font-bold capitalize">{formatDestination(payoutDestination)}</span>
              </div>
            </div>
            <div className="mt-4 rounded-[20px] bg-stone-950 px-4 py-3 text-sm leading-6 text-stone-100">
              Avok currently holds {formatMoney(heldAmount)} for this checkout session. After delivery confirmation or approved dispute resolution, {formatMoney(recipientNet)} goes to the recipient and {formatMoney(releaseFee)} is kept as the external release charge only when funds leave to MoMo or bank.
            </div>
          </div>

          <div className="card rounded-[28px] p-6">
            <h3 className="text-xl font-bold">Checkout and sandbox payment</h3>
            {canFund ? (
              <>
                <p className="mt-2 text-sm text-stone-600">
                  Initiate the payment path, then use the sandbox buttons to simulate whether the money was successfully moved into escrow.
                </p>
                <form
                  className="mt-5 space-y-4"
                  onSubmit={(event) => {
                    event.preventDefault();
                    paymentMutation.mutate(paymentForm);
                  }}
                >
                  <select className="field" value={paymentForm.momo_provider} onChange={(event) => setPaymentForm((prev) => ({ ...prev, momo_provider: event.target.value }))}>
                    <option value="mtn">MTN</option>
                    <option value="telecel">Telecel</option>
                    <option value="airtel_tigo">AirtelTigo</option>
                  </select>
                  <input className="field" value={paymentForm.momo_number} onChange={(event) => setPaymentForm((prev) => ({ ...prev, momo_number: event.target.value }))} placeholder="0241111111" />
                  <select className="field" value={paymentForm.funding_source} onChange={(event) => setPaymentForm((prev) => ({ ...prev, funding_source: event.target.value }))}>
                    <option value="verified_account">Pay from Avok verified account</option>
                    <option value="momo">Pay from MoMo directly into escrow</option>
                    <option value="bank">Pay from bank directly into escrow</option>
                  </select>
                  <select className="field" value={paymentForm.payout_destination} onChange={(event) => setPaymentForm((prev) => ({ ...prev, payout_destination: event.target.value }))}>
                    <option value="verified_account">Release to Avok verified account</option>
                    <option value="momo">Release to MoMo directly</option>
                    <option value="bank">Release to bank directly</option>
                  </select>
                  <button className="btn-primary w-full" type="submit">
                    {paymentMutation.isPending ? "Starting payment..." : "Initiate payment"}
                  </button>
                </form>

                {paymentMutation.data ? (
                  <div className="mt-4 space-y-3">
                    <div className="rounded-[22px] bg-stone-950 p-4 text-xs text-emerald-200">
                      <pre className="overflow-auto whitespace-pre-wrap">{JSON.stringify(paymentMutation.data, null, 2)}</pre>
                    </div>
                    <div className="flex flex-wrap gap-3">
                      <button className="btn-primary" onClick={() => sandboxSuccessMutation.mutate(paymentMutation.data.transaction_reference)} type="button">
                        Mark payment successful
                      </button>
                      <button className="btn-danger" onClick={() => sandboxFailMutation.mutate(paymentMutation.data.transaction_reference)} type="button">
                        Mark payment failed
                      </button>
                    </div>
                  </div>
                ) : null}

                {sandboxSuccessMutation.data ? <p className="mt-4 rounded-2xl bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">Payment moved into escrow successfully.</p> : null}
              </>
            ) : (
              <div className="mt-4 rounded-[22px] bg-stone-50 p-4 text-sm leading-6 text-stone-700">
                {order.escrow_status === "pending_payment"
                  ? "Only the payer can move money into escrow. You can still monitor the checkout details and wait for funding."
                  : "Funding is no longer available on this checkout session. This panel stays visible so both sides can understand how the escrow amount was calculated."}
              </div>
            )}
            <div className="mt-4 rounded-[22px] bg-stone-50 p-4 text-sm leading-6 text-stone-700">
              <span className="font-semibold">Rule preview:</span>{" "}
              {paymentForm.funding_source === "verified_account"
                ? "No charge is applied when the payer uses verified Avok balance for the purchase."
                : "A 1% capped fee applies because money is entering escrow directly from external rails."}{" "}
              {paymentForm.payout_destination === "verified_account"
                ? "Release into a verified Avok account should be free."
                : "A 1% capped fee applies because money is leaving escrow directly to external rails."}
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div className="card rounded-[28px] p-6">
            <h3 className="text-xl font-bold">Delivery confirmation</h3>
            <div className="mt-4 flex flex-wrap gap-3">
              {canGenerateDeliveryOtp ? (
                <button className="btn-secondary" type="button" onClick={() => recipientOtpMutation.mutate()}>
                  Recipient generate OTP
                </button>
              ) : null}
              {canConfirmDelivery ? (
                <button className="btn-primary" type="button" onClick={() => payerConfirmMutation.mutate()}>
                  Payer confirm delivery
                </button>
              ) : null}
            </div>
            {recipientOtpMutation.data ? (
              <div className="mt-4 rounded-[22px] bg-amber-50 p-4 text-sm text-amber-900">
                <p className="font-semibold">Generated OTP</p>
                <p className="mt-1 text-lg font-bold tracking-[0.2em]">{recipientOtpMutation.data.otp}</p>
              </div>
            ) : null}
            {canSubmitDeliveryOtp ? (
              <>
                <div className="mt-5">
                  <OTPInput value={otp} onChange={setOtp} label="Recipient submits OTP after handover" />
                </div>
                <button className="btn-primary mt-5 w-full" type="button" onClick={() => recipientConfirmMutation.mutate(otp)}>
                  Confirm delivery with OTP
                </button>
              </>
            ) : order.recipient_id || order.seller_id ? (
              <div className="mt-5 rounded-[22px] bg-stone-50 p-4 text-sm leading-6 text-stone-700">
                {canConfirmDelivery
                  ? "Only the registered recipient can generate and submit the delivery OTP. You can release the escrow after handover by using payer confirmation."
                  : "OTP actions appear only for the registered recipient at the right stage of delivery. You can still monitor the escrow timeline here."}
              </div>
            ) : (
              <div className="mt-5 rounded-[22px] bg-stone-50 p-4 text-sm leading-6 text-stone-700">
                This checkout session pays an external recipient. Payer confirmation is the primary release path here unless a dispute is opened.
              </div>
            )}
          </div>

          <div className="card rounded-[28px] p-6">
            <h3 className="text-xl font-bold">What happens next</h3>
            <div className="mt-4 space-y-3">
              {timeline.map((step) => (
                <article key={step.title} className="rounded-[22px] bg-stone-50 p-4">
                  <p className="font-bold">{step.title}</p>
                  <p className="mt-2 text-sm leading-6 text-stone-600">{step.body}</p>
                </article>
              ))}
            </div>
            <div className="mt-4 rounded-[22px] bg-emerald-50 p-4 text-sm leading-6 text-emerald-900">
              <span className="font-semibold">Testing tip:</span> after a successful sandbox payment, refresh this page and then try payer confirmation or payout-recipient OTP confirmation to see the escrow status move toward release. For non-user escrow flows, this screen should represent a temporary escrow account that closes after clean release.
            </div>
          </div>
        </section>
      </div>

      <div className="flex flex-wrap gap-3">
        <Link href="/checkout/new" className="btn-secondary">
          Create another session
        </Link>
        <Link href="/wallet" className="btn-secondary">
          Check wallet balances
        </Link>
      </div>
    </div>
  );
}
