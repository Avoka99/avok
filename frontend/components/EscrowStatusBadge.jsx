const toneMap = {
  held: "bg-emerald-50 text-emerald-800 border-emerald-200",
  pending: "bg-amber-50 text-amber-800 border-amber-200",
  released: "bg-sky-50 text-sky-800 border-sky-200",
  disputed: "bg-rose-50 text-rose-800 border-rose-200",
  failed: "bg-stone-100 text-stone-700 border-stone-200"
};

const labelMap = {
  held: "Funds held securely",
  pending: "Awaiting payment",
  released: "Funds released",
  disputed: "Under dispute review",
  failed: "Payment failed"
};

export default function EscrowStatusBadge({ status = "pending" }) {
  const normalized = String(status).toLowerCase();
  const className = toneMap[normalized] || toneMap.pending;
  const label = labelMap[normalized] || status;

  return (
    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-bold ${className}`}>
      {label}
    </span>
  );
}
