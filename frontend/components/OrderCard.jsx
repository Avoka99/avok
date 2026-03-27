import Link from "next/link";
import EscrowStatusBadge from "@/components/EscrowStatusBadge";

function formatMoney(value) {
  const amount = Number(value || 0);
  return new Intl.NumberFormat("en-GH", {
    style: "currency",
    currency: "GHS",
    maximumFractionDigits: 2
  }).format(amount);
}

export default function OrderCard({ order, actions }) {
  const reference = order.order_reference || order.reference || "Order";
  const productPrice = Number(order.product_price ?? order.amount ?? order.price ?? 0);
  const entryFee = Number(order.platform_fee ?? order.buyer_fee ?? productPrice * 0.01);
  const totalAmount = Number(order.total_amount ?? productPrice + entryFee);

  return (
    <article className="card rounded-[24px] p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">
            {reference}
          </p>
          <h3 className="mt-2 text-xl font-bold">{order.title || order.product_name || "Checkout session"}</h3>
          <p className="mt-2 text-sm leading-6 text-stone-600">
            {order.description || "Escrow-backed payment protected until delivery is confirmed."}
          </p>
        </div>
        <EscrowStatusBadge status={order.escrow_status || order.status || "pending"} />
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-[20px] bg-stone-50 p-4">
          <p className="text-sm text-stone-500">Price</p>
          <p className="mt-1 text-lg font-bold">{formatMoney(productPrice)}</p>
        </div>
        <div className="rounded-[20px] bg-stone-50 p-4">
          <p className="text-sm text-stone-500">Entry fee</p>
          <p className="mt-1 text-lg font-bold">{formatMoney(entryFee)}</p>
        </div>
        <div className="rounded-[20px] bg-stone-50 p-4">
          <p className="text-sm text-stone-500">Delivery status</p>
          <p className="mt-1 text-lg font-bold">{order.delivery_status || order.status || "Pending"}</p>
        </div>
        <div className="rounded-[20px] bg-stone-50 p-4">
          <p className="text-sm text-stone-500">Escrow total</p>
          <p className="mt-1 text-lg font-bold">{formatMoney(totalAmount)}</p>
        </div>
      </div>

      <div className="mt-3 rounded-[20px] bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
        <span className="font-semibold">Who holds the money:</span>{" "}
        {order.escrow_status === "released" || order.escrow_status === "completed" ? "Recipient balance" : "Avok escrow"}
      </div>

      <div className="mt-5 flex flex-wrap gap-3">
        <Link href={`/checkout/${reference}`} className="btn-secondary">
          View escrow details
        </Link>
        {actions}
      </div>

      {actions ? null : (
        <div className="mt-5">
          <Link href={`/checkout/${reference}`} className="btn-secondary inline-flex">
            Open checkout session
          </Link>
        </div>
      )}
    </article>
  );
}
