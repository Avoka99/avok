"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import AdminReviewPanel from "@/components/AdminReviewPanel";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";

export default function AdminDashboardPage() {
  const user = useAuthStore(state => state.user);
  const queryClient = useQueryClient();
  const canAccess = Boolean(user && (user.role === "admin" || user.role === "super_admin" || user.is_superuser));

  const [selectedDisputeId, setSelectedDisputeId] = useState(null);

  const disputesQuery = useQuery({
    queryKey: ["admin-dispute-queue"],
    enabled: canAccess,
    queryFn: async () => {
      const response = await api.get("/admin/disputes/queue");
      return response.data;
    }
  });

  const actionsQuery = useQuery({
    queryKey: ["admin-actions"],
    enabled: canAccess,
    queryFn: async () => {
      const response = await api.get("/admin/actions");
      return response.data;
    }
  });

  const resolveMutation = useMutation({
    mutationFn: async ({ disputeId, action }) => {
      const response = await api.post(`/disputes/${disputeId}/resolve`, {
        dispute_id: disputeId,
        action,
        notes: `Admin review proposed ${action}.`
      });
      return response.data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-dispute-queue"] }),
        queryClient.invalidateQueries({ queryKey: ["admin-actions"] })
      ]);
    }
  });

  const approveMutation = useMutation({
    mutationFn: async (actionId) => {
      const response = await api.post(`/disputes/actions/${actionId}/approve`);
      return response.data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["admin-dispute-queue"] }),
        queryClient.invalidateQueries({ queryKey: ["admin-actions"] })
      ]);
    }
  });

  const disputes = Array.isArray(disputesQuery.data) ? disputesQuery.data : [];
  const selectedDispute = useMemo(() => {
    if (!disputes.length) {
      return null;
    }
    if (selectedDisputeId) {
      return disputes.find((item) => item.dispute_id === selectedDisputeId) || disputes[0];
    }
    return disputes[0];
  }, [disputes, selectedDisputeId]);

  const pendingActions = Array.isArray(actionsQuery.data)
    ? actionsQuery.data.filter((action) => action.status === "pending")
    : [];
  const recentActions = Array.isArray(actionsQuery.data) ? actionsQuery.data.slice(0, 5) : [];

  if (!canAccess) {
    return <div className="p-10 text-center text-rose-600 font-bold">Unauthorized: This area requires elevated privileges.</div>;
  }

  return (
    <div className="space-y-5">
      <section className="card rounded-[28px] p-6">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Admin dashboard</p>
        <h2 className="mt-3 text-3xl font-black">Review evidence, compare decisions, and only finalize disputes when admins agree.</h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-stone-600">
          The admin view is structured to reduce rushed judgments. Evidence, listing context, and dual-admin decisions stay visible in one screen.
        </p>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <section className="card rounded-[28px] p-6">
          <h3 className="text-xl font-bold">Open disputes</h3>
          {disputesQuery.isLoading ? <p className="mt-4 text-sm text-stone-600">Loading disputes...</p> : null}
          {!disputesQuery.isLoading && disputes.length === 0 ? (
            <div className="mt-4 rounded-[24px] bg-stone-50 p-5 text-sm leading-6 text-stone-600">
              There are no disputes yet. When a payer opens one, evidence and review status will appear here.
            </div>
          ) : null}
          <div className="mt-4 space-y-4">
            {disputes.map((dispute) => (
              <article
                key={dispute.dispute_id || dispute.dispute_reference}
                className={`rounded-[24px] p-5 transition ${
                  selectedDispute?.dispute_id === dispute.dispute_id ? "bg-amber-50 ring-1 ring-amber-200" : "bg-stone-50"
                }`}
              >
                <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">
                  {dispute.dispute_reference || dispute.dispute_id || "Dispute"}
                </p>
                <h4 className="mt-2 text-lg font-bold">
                  {dispute.session_reference || dispute.order_reference || "Checkout session dispute"}
                </h4>
                <p className="mt-2 text-sm leading-6 text-stone-600">{dispute.description}</p>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <div className="rounded-[18px] bg-white px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.18em] text-stone-500">Status</p>
                    <p className="mt-2 font-bold capitalize">{String(dispute.dispute_status || "").replaceAll("_", " ")}</p>
                  </div>
                  <div className="rounded-[18px] bg-white px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.18em] text-stone-500">Type</p>
                    <p className="mt-2 font-bold capitalize">{String(dispute.dispute_type || "").replaceAll("_", " ")}</p>
                  </div>
                  <div className="rounded-[18px] bg-white px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.18em] text-stone-500">Evidence files</p>
                    <p className="mt-2 font-bold">{dispute.evidence_count || 0}</p>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-3">
                  <button className="btn-secondary" type="button" onClick={() => setSelectedDisputeId(dispute.dispute_id)}>
                    Review this dispute
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <div className="space-y-4">
          <AdminReviewPanel
            dispute={selectedDispute}
            onResolve={(action) => {
              if (!selectedDispute?.dispute_id) return;
              resolveMutation.mutate({ disputeId: selectedDispute.dispute_id, action });
            }}
            onApprove={() => {
              if (!selectedDispute?.latest_action_id) return;
              approveMutation.mutate(selectedDispute.latest_action_id);
            }}
            isResolving={resolveMutation.isPending}
            isApproving={approveMutation.isPending}
          />
          <section className="card rounded-[24px] p-5">
            <h3 className="text-xl font-bold">Evidence preview</h3>
            {selectedDispute?.evidence_urls?.length ? (
              <div className="mt-4 space-y-3">
                {selectedDispute.evidence_urls.map((url) => (
                  <div key={url} className="rounded-[22px] bg-stone-100 p-5 text-sm text-stone-600 break-all">
                    {url}
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div className="rounded-[22px] bg-stone-100 p-5 text-sm text-stone-600">Uploaded buyer or payer evidence will appear here.</div>
                <div className="rounded-[22px] bg-stone-100 p-5 text-sm text-stone-600">Imported product details and checkout context will appear here.</div>
              </div>
            )}
          </section>
          <section className="card rounded-[24px] p-5">
            <h3 className="text-xl font-bold">Pending approval queue</h3>
            {actionsQuery.isLoading ? <p className="mt-4 text-sm text-stone-600">Loading admin actions...</p> : null}
            {!actionsQuery.isLoading && pendingActions.length === 0 ? (
              <p className="mt-4 text-sm leading-6 text-stone-600">No pending admin approvals right now.</p>
            ) : null}
            <div className="mt-4 space-y-3">
              {pendingActions.map((action) => (
                <div key={action.id} className="rounded-[20px] bg-stone-50 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-stone-500">{action.action_reference}</p>
                  <p className="mt-2 font-bold capitalize">{String(action.resolution || action.action_type).replaceAll("_", " ")}</p>
                  <p className="mt-1 text-sm text-stone-600">
                    Approvals: {action.approvals_received}/{action.approvals_required}
                  </p>
                </div>
              ))}
            </div>
          </section>
          <section className="card rounded-[24px] p-5">
            <h3 className="text-xl font-bold">Recent admin actions</h3>
            {!actionsQuery.isLoading && recentActions.length === 0 ? (
              <p className="mt-4 text-sm leading-6 text-stone-600">No admin actions have been recorded yet.</p>
            ) : null}
            <div className="mt-4 space-y-3">
              {recentActions.map((action) => (
                <div key={action.id} className="rounded-[20px] bg-stone-50 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-stone-500">{action.action_reference}</p>
                      <p className="mt-2 font-bold capitalize">{String(action.resolution || action.action_type).replaceAll("_", " ")}</p>
                      <p className="mt-1 text-sm text-stone-600">{action.reason}</p>
                    </div>
                    <span className="rounded-full bg-white px-3 py-1 text-xs font-bold capitalize text-stone-700">
                      {String(action.status || "").replaceAll("_", " ")}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
