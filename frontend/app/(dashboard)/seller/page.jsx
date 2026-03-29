"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Truck, Wallet } from "lucide-react";
import OrderCard from "@/components/OrderCard";
import OTPInput from "@/components/OTPInput";
import { api } from "@/lib/api";

export default function SellerDashboardPage() {
  const [page, setPage] = useState(0);
  const limit = 10;
  const [allOrders, setAllOrders] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [otp, setOtp] = useState("");

  const ordersQuery = useQuery({
    queryKey: ["seller-orders", page],
    queryFn: async () => {
      const response = await api.get(`/checkout/sessions?role=seller&skip=${page * limit}&limit=${limit}`);
      return response.data;
    }
  });

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

  const walletQuery = useQuery({
    queryKey: ["wallet"],
    queryFn: async () => {
      const response = await api.get("/wallet/balance");
      return response.data;
    }
  });

  const walletBalance = walletQuery.data?.balance || walletQuery.data?.available_balance || 0;

  return (
    <div className="space-y-5">
      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="card rounded-[28px] p-6">
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">My receipts</p>
          <h2 className="mt-3 text-3xl font-black">Track incoming escrow payouts and see exactly when funds are released.</h2>
          <p className="mt-3 max-w-2xl text-sm leading-7 text-stone-600">
            See every checkout session where you are the recipient, track shipment milestones, and know exactly when escrow will release.
          </p>
        </div>
        <div className="card rounded-[28px] bg-stone-900 p-6 text-white">
          <div className="flex items-center gap-3">
            <Wallet className="h-6 w-6" />
            <div>
              <p className="text-sm text-stone-300">Estimated earnings</p>
              <p className="mt-1 text-3xl font-black">GHS {Number(walletBalance).toLocaleString()}</p>
            </div>
          </div>
          <p className="mt-4 text-sm leading-6 text-stone-200">Recipient release fees only apply when funds leave escrow directly to bank or MoMo.</p>
          <Link href="/wallet" className="btn-secondary mt-5 inline-flex bg-white text-stone-900">
            Open wallet view
          </Link>
        </div>
      </section>

      <section className="space-y-4">
        {allOrders.length === 0 && !ordersQuery.isLoading ? (
          <div className="card rounded-[24px] p-6">
            <h3 className="text-xl font-bold">No active payout sessions</h3>
            <p className="mt-2 text-sm text-stone-600">Sessions connected to your Avok account will appear here when payers use Avok to pay you.</p>
          </div>
        ) : (
          <>
            {allOrders.map((order) => (
              <OrderCard
                key={order.order_reference || order.id}
                order={order}
                actions={
                  <>
                    <Link href={`/checkout/${order.session_reference || order.order_reference}`} className="btn-secondary inline-flex items-center gap-2">
                      <Truck className="h-4 w-4" />
                      Open shipment flow
                    </Link>
                    <Link href={`/checkout/${order.session_reference || order.order_reference}`} className="btn-primary">
                      View escrow details
                    </Link>
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
              <p className="py-4 text-center text-sm text-stone-500">End of payout history.</p>
            ) : null}
          </>
        )}
      </section>

      <section className="card rounded-[28px] p-6">
        <h3 className="text-xl font-bold">Enter delivery OTP</h3>
        <p className="mt-2 text-sm text-stone-600">
          When delivery happens, submit the OTP so the system can verify the handover and move the order to the next step.
        </p>
        <div className="mt-5">
          <OTPInput value={otp} onChange={setOtp} />
        </div>
        <p className="mt-5 rounded-[20px] bg-stone-50 px-4 py-3 text-sm leading-6 text-stone-700">
          Use any session above to open its checkout detail page, generate the delivery OTP, and complete recipient confirmation from the live escrow flow.
        </p>
      </section>
    </div>
  );
}
