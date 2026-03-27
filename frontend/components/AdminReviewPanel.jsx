function formatDecision(decision) {
  if (!decision) {
    return "Pending";
  }

  return String(decision).replaceAll("_", " ");
}

export default function AdminReviewPanel({ dispute, onResolve, onApprove, isResolving, isApproving }) {
  if (!dispute) {
    return (
      <section className="card rounded-[24px] p-5">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Multi-admin approval</p>
        <h3 className="mt-2 text-xl font-bold">Dispute review panel</h3>
        <p className="mt-3 text-sm leading-6 text-stone-600">
          Once a dispute is opened, both admin review decisions will appear here before final action is taken.
        </p>
      </section>
    );
  }

  const latestResolution = formatDecision(dispute?.latest_action_resolution);
  const approvalsReceived = dispute?.approvals_received || 0;
  const approvalsRequired = dispute?.approvals_required || 0;
  const ready = approvalsRequired > 0 && approvalsReceived >= approvalsRequired;

  return (
    <section className="card rounded-[24px] p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Multi-admin approval</p>
          <h3 className="mt-2 text-xl font-bold">Dispute review panel</h3>
          <p className="mt-2 text-sm leading-6 text-stone-600">
            Final action is only completed when the required number of administrators approve the same outcome.
          </p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-bold ${
            ready ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
          }`}
        >
          {ready ? "Ready to finalize" : "Waiting for consensus"}
        </span>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <div className="rounded-[20px] bg-stone-50 p-4">
          <p className="text-sm text-stone-500">Latest proposed outcome</p>
          <p className="mt-2 text-lg font-bold capitalize">{latestResolution}</p>
        </div>
        <div className="rounded-[20px] bg-stone-50 p-4">
          <p className="text-sm text-stone-500">Approvals progress</p>
          <p className="mt-2 text-lg font-bold">{approvalsReceived}/{approvalsRequired || 0}</p>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <button className="btn-secondary" type="button" onClick={() => onResolve?.("payer_wins")} disabled={isResolving}>
          {isResolving ? "Submitting..." : "Propose refund to payer"}
        </button>
        <button className="btn-secondary" type="button" onClick={() => onResolve?.("recipient_wins")} disabled={isResolving}>
          {isResolving ? "Submitting..." : "Propose release to recipient"}
        </button>
        <button className="btn-secondary" type="button" onClick={() => onResolve?.("refund")} disabled={isResolving}>
          {isResolving ? "Submitting..." : "Propose full refund"}
        </button>
        <button className="btn-primary" type="button" onClick={() => onApprove?.()} disabled={isApproving || !dispute?.latest_action_id}>
          {isApproving ? "Approving..." : "Approve latest action"}
        </button>
      </div>
    </section>
  );
}
