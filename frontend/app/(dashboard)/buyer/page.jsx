"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, PlusCircle } from "lucide-react";
import OrderCard from "@/components/OrderCard";
import OTPInput from "@/components/OTPInput";
import DisputeUpload from "@/components/DisputeUpload";
import { api } from "@/lib/api";

export default function BuyerDashboardPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const limit = 10;

  const ordersQuery = useQuery({
    queryKey: ["buyer-orders", page],
    queryFn: async () => {
      const response = await api.get(`/checkout/sessions?role=buyer&skip=${page * limit}&limit=${limit}`);
      return response.data;
    }
  });

  const [allOrders, setAllOrders] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [selectedReference, setSelectedReference] = useState(null);
  const [otp, setOtp] = useState("");
  const [evidenceFiles, setEvidenceFiles] = useState([]);
  const [disputeText, setDisputeText] = useState("");

  useMemo(() => {
    if (ordersQuery.data) {
      const items = ordersQuery.data.items || [];
      if (page === 0) {
        setAllOrders(items);
      } else {
        setAllOrders((prev) => {
          const newItems = items.filter(
            (item) => !prev.some((p) => (p.order_reference || p.id) === (item.order_reference || item.id))
          );
          return [...prev, ...newItems];
        });
      }
      setHasMore(ordersQuery.data.has_more);
    }
  }, [ordersQuery.data, page]);

  const disputeMutation = useMutation({
    mutationFn: async (payload) => {
      const response = await api.post("/disputes", payload);
      return response.data;
    },
    onSuccess: async (dispute) => {
      if (evidenceFiles.length > 0 && dispute?.id) {
        const formData = new FormData();
        evidenceFiles.forEach((file) => formData.append("files", file));
        await api.post(`/disputes/${dispute.id}/evidence`, formData, {
          headers: { "Content-Type": "multipart/form-data" }
        });
      }

      await queryClient.invalidateQueries({ queryKey: ["buyer-orders"] });
      setPage(0); // Reset to first page
      setEvidenceFiles([]);
      setDisputeText("");
    }
  });

  function submitDispute(reference) {
    setSelectedReference(reference);
    disputeMutation.mutate({
      session_reference: reference,
      dispute_type: "other",
      description: disputeText
    });
  }

  return (
    <div className="space-y-5">
      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="card rounded-[28px] p-6">
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">My payments</p>
          <h2 className="mt-3 text-3xl font-black">Track every checkout session and always know who holds the money.</h2>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-stone-600">
            See every checkout session where you are the payer, follow delivery progress, and raise disputes without guessing what happens next.
          </p>
        </div>
        <div className="card rounded-[28px] bg-emerald-900 p-6 text-white">
          <p className="text-sm text-emerald-100">Escrow promise</p>
          <p className="mt-3 text-3xl font-black">Funds stay protected until you confirm delivery.</p>
          <p className="mt-3 text-sm leading-6 text-emerald-50">If something goes wrong, raise a dispute and attach proof directly from your phone.</p>
          <Link href="/checkout/new" className="btn-secondary mt-5 inline-flex bg-white text-emerald-900">
            Create checkout session
          </Link>
        </div>
      </section>

      <section className="space-y-4">
        {allOrders.length === 0 && !ordersQuery.isLoading ? (
          <div className="card rounded-[24px] p-6">
            <h3 className="text-xl font-bold">No payment sessions yet</h3>
            <p className="mt-2 text-sm text-stone-600">Create your first session from checkout or through an embedded Pay with Avok flow.</p>
          </div>
        ) : (
          <>
            {allOrders.map((order) => (
              <OrderCard
                key={order.order_reference || order.id}
                order={order}
                actions={
                  <>
                    <Link href={`/checkout/${order.session_reference || order.order_reference}`} className="btn-primary inline-flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4" />
                      Open checkout
                    </Link>
                    <button
                      className="btn-danger inline-flex items-center gap-2"
                      onClick={() => setSelectedReference(order.session_reference || order.order_reference)}
                    >
                      <AlertTriangle className="h-4 w-4" />
                      Select for dispute
                    </button>
                  </>
                }
              />
            ))}
            
            {hasMore ? (
              <button
                className="btn-secondary w-full py-4 text-stone-700"
                onClick={() => setPage((prev) => prev + 1)}
                disabled={ordersQuery.isLoading}
              >
                {ordersQuery.isLoading ? "Loading more..." : "Load more sessions"}
              </button>
            ) : allOrders.length > 0 ? (
              <p className="py-4 text-center text-sm text-stone-500">You've reached the end of your session history.</p>
            ) : null}
          </>
        )}
      </section>

      <section className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <div className="card rounded-[28px] p-6">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-emerald-50 p-3 text-emerald-700">
              <PlusCircle className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-xl font-bold">Confirm with delivery OTP</h3>
              <p className="text-sm text-stone-600">Enter the recipient-shared OTP when the item arrives safely.</p>
            </div>
          </div>
          <div className="mt-5">
            <OTPInput value={otp} onChange={setOtp} />
          </div>
          <Link href={selectedReference ? `/checkout/${selectedReference}` : "/checkout/new"} className="btn-primary mt-5 inline-flex w-full justify-center">
            Submit OTP from checkout detail
          </Link>
        </div>

        <div className="space-y-4">
          <DisputeUpload files={evidenceFiles} onFilesChange={setEvidenceFiles} />
          <div className="card rounded-[24px] p-5">
            <label className="mb-2 block text-sm font-semibold text-stone-700">Dispute description</label>
            <textarea
              value={disputeText}
              onChange={(event) => setDisputeText(event.target.value)}
              rows={5}
              className="field"
              placeholder="Explain what happened, what you received, and why escrow should remain locked."
            />
            <p className="mt-3 text-xs uppercase tracking-[0.18em] text-stone-500">
              Selected session: {selectedReference || "Choose a session by pressing Raise dispute on one of your checkout sessions above."}
            </p>
            {disputeMutation.isSuccess ? (
              <p className="mt-3 rounded-2xl bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">Dispute submitted successfully.</p>
            ) : null}
            {disputeMutation.isError ? (
              <p className="mt-3 rounded-2xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">{disputeMutation.error.message}</p>
            ) : null}
            <button
              className="btn-primary mt-4 w-full"
              type="button"
              disabled={!selectedReference || disputeText.trim().length < 10 || disputeMutation.isPending}
              onClick={() => submitDispute(selectedReference)}
            >
              {disputeMutation.isPending ? "Submitting dispute..." : "Submit dispute for selected session"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
