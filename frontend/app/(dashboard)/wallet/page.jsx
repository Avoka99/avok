"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { calculateCappedFee, formatGhs } from "@/lib/fees";

const fallbackBalance = {
  available_balance: 0,
  pending_balance: 0,
  escrow_balance: 0,
  total_balance: 0
};

function validateDepositPayload(payload) {
  const amount = Number(payload.amount);
  if (!Number.isFinite(amount) || amount <= 0) {
    return "Enter a deposit amount greater than zero.";
  }
  const label = String(payload.source_label || "").trim();
  if (payload.source_type === "momo") {
    if (label.length < 10) {
      return "Enter a valid mobile money number (at least 10 digits).";
    }
  } else if (label.length < 6) {
    return "Enter your bank account number (at least 6 characters).";
  }
  return null;
}

export default function WalletPage() {
  const queryClient = useQueryClient();
  const [depositFormError, setDepositFormError] = useState("");
  const [deposit, setDeposit] = useState({
    amount: "",
    source_type: "momo",
    source_label: "",
    momo_provider: "mtn"
  });
  const [withdrawal, setWithdrawal] = useState({
    amount: "",
    destination_type: "momo",
    destination_reference: "",
    momo_provider: "mtn",
    bank_name: ""
  });

  const [transactionPage, setTransactionPage] = useState(0);
  const transactionLimit = 10;
  const [allTransactions, setAllTransactions] = useState([]);
  const [hasMoreTransactions, setHasMoreTransactions] = useState(false);

  const balanceQuery = useQuery({
    queryKey: ["wallet-balance"],
    queryFn: async () => {
      const response = await api.get("/wallet/balance");
      return response.data;
    }
  });

  const transactionsQuery = useQuery({
    queryKey: ["wallet-transactions", transactionPage],
    queryFn: async () => {
      const response = await api.get(`/wallet/transactions?skip=${transactionPage * transactionLimit}&limit=${transactionLimit}`);
      return response.data;
    }
  });

  useMemo(() => {
    if (transactionsQuery.data) {
      const items = transactionsQuery.data.items || [];
      if (transactionPage === 0) {
        setAllTransactions(items);
      } else {
        setAllTransactions((prev) => {
          const newItems = items.filter(
            (item) => !prev.some((p) => p.reference === item.reference)
          );
          return [...prev, ...newItems];
        });
      }
      setHasMoreTransactions(transactionsQuery.data.has_more);
    }
  }, [transactionsQuery.data, transactionPage]);

  const withdrawMutation = useMutation({
    mutationFn: async (payload) => {
      const response = await api.post("/wallet/withdraw", {
        amount: Number(payload.amount),
        destination_type: payload.destination_type,
        destination_reference: payload.destination_reference,
        momo_provider: payload.destination_type === "momo" ? payload.momo_provider : null,
        bank_name: payload.destination_type === "bank" ? payload.bank_name : null
      });
      return response.data;
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["wallet-balance"] }),
        queryClient.invalidateQueries({ queryKey: ["wallet-transactions"] })
      ]);
    },
  });

  const depositMutation = useMutation({
    mutationFn: async (payload) => {
      const response = await api.post("/wallet/deposit", {
        amount: Number(payload.amount),
        source_type: payload.source_type,
        source_reference:
          payload.source_type === "momo"
            ? `${payload.momo_provider}:${String(payload.source_label).trim()}`
            : String(payload.source_label).trim()
      });
      return response.data;
    },
    onMutate: () => {
      setDepositFormError("");
    },
    onSuccess: async () => {
      setDepositFormError("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["wallet-balance"] }),
        queryClient.invalidateQueries({ queryKey: ["wallet-transactions"] })
      ]);
    },
    onError: (err) => {
      setDepositFormError(err?.message || "Deposit could not be completed.");
    }
  });

  const balance = balanceQuery.data || fallbackBalance;
  const transactions = useMemo(() => {
    if (Array.isArray(transactionsQuery.data)) {
      return transactionsQuery.data;
    }
    return [];
  }, [transactionsQuery.data]);

  const depositFee = calculateCappedFee(deposit.amount);
  const withdrawalFee = calculateCappedFee(withdrawal.amount);
  const depositNet = Math.max(Number(deposit.amount || 0) - depositFee, 0);
  const withdrawalNet = Math.max(Number(withdrawal.amount || 0) - withdrawalFee, 0);

  return (
    <div className="space-y-5">
      <section className="card rounded-[28px] p-6">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Wallet</p>
        <h2 className="mt-3 text-3xl font-black">One verified Avok account can hold deposits and escrow releases for payment use.</h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-stone-600">
          Deposit from MoMo or bank, receive funds from escrow, pay for purchases with no extra verified-balance fee, and withdraw back out when needed. Deposit and withdrawal fees are 1% and cap at GHS 30.
        </p>
        <div className="mt-4 rounded-[22px] bg-emerald-50 p-4 text-sm leading-6 text-emerald-900">
          Money already inside your verified Avok account can be used for purchases without any extra usage charge. Fees only apply when money moves in from or out to external rails.
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="card rounded-[24px] p-5">
          <p className="text-sm text-stone-500">Available balance</p>
          <p className="mt-2 text-2xl font-black">GHS {Number(balance.available_balance).toFixed(2)}</p>
        </div>
        <div className="card rounded-[24px] p-5">
          <p className="text-sm text-stone-500">Escrow balance</p>
          <p className="mt-2 text-2xl font-black">GHS {Number(balance.escrow_balance).toFixed(2)}</p>
        </div>
        <div className="card rounded-[24px] p-5">
          <p className="text-sm text-stone-500">Pending fees</p>
          <p className="mt-2 text-2xl font-black">GHS {Number(balance.pending_balance).toFixed(2)}</p>
        </div>
        <div className="card rounded-[24px] p-5">
          <p className="text-sm text-stone-500">Total wallet value</p>
          <p className="mt-2 text-2xl font-black">GHS {Number(balance.total_balance).toFixed(2)}</p>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <section className="card rounded-[28px] p-6">
          <h3 className="text-xl font-bold">Deposit into verified account</h3>
          <p className="mt-2 text-sm leading-6 text-stone-600">
            Users are charged only when moving money into the verified account from MoMo or bank rails. Purchases from the verified account should not incur this charge.
          </p>
          <form
            className="mt-5 space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              depositMutation.mutate(deposit);
            }}
          >
            <input
              className="field"
              value={deposit.amount}
              onChange={(event) => setDeposit((prev) => ({ ...prev, amount: event.target.value }))}
              placeholder="Deposit amount"
            />
            <select
              className="field"
              value={deposit.source_type}
              onChange={(event) => setDeposit((prev) => ({ ...prev, source_type: event.target.value }))}
            >
              <option value="momo">Mobile money</option>
              <option value="bank">Bank transfer</option>
            </select>
            <div>
              <label className="mb-2 block text-sm font-semibold text-stone-700">
                {deposit.source_type === "momo" ? "Mobile money number" : "Bank account"}
              </label>
              <input
                className="field"
                value={deposit.source_label}
                onChange={(event) => setDeposit((prev) => ({ ...prev, source_label: event.target.value }))}
                placeholder={deposit.source_type === "momo" ? "e.g. 0241234567" : "Account number you are transferring from"}
                autoComplete="off"
              />
            </div>
            {deposit.source_type === "momo" ? (
              <select
                className="field"
                value={deposit.momo_provider}
                onChange={(event) => setDeposit((prev) => ({ ...prev, momo_provider: event.target.value }))}
              >
                <option value="mtn">MTN</option>
                <option value="telecel">Telecel</option>
                <option value="airtel_tigo">AirtelTigo</option>
              </select>
            ) : null}
            <button className="btn-primary w-full" type="submit" disabled={depositMutation.isPending}>
              {depositMutation.isPending ? "Depositing..." : "Deposit into Avok"}
            </button>
          </form>

          {depositFormError ? (
            <p className="mt-4 rounded-2xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-800" role="alert">
              {depositFormError}
            </p>
          ) : null}

          <div className="mt-5 space-y-3">
            <div className="rounded-[20px] bg-stone-50 px-4 py-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-stone-600">Deposit fee</span>
                <span className="font-bold">{formatGhs(depositFee)}</span>
              </div>
            </div>
            <div className="rounded-[20px] bg-stone-50 px-4 py-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-stone-600">Amount credited to verified account</span>
                <span className="font-bold">{formatGhs(depositNet)}</span>
              </div>
            </div>
            <div className="rounded-[20px] bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
              Verified accounts are charged only on money entering from MoMo or bank rails and on money leaving back to them. Paying with existing Avok balance should stay fee-free.
            </div>
          </div>
          {depositMutation.isSuccess && depositMutation.data ? (
            <div className="mt-4 space-y-2 rounded-[22px] bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
              <p className="font-bold">Deposit completed</p>
              <p>
                Reference: <span className="font-mono font-semibold">{depositMutation.data.transaction_reference}</span>
              </p>
              <p className="text-emerald-800">
                Credited about GHS {Number(depositMutation.data.net_amount || 0).toFixed(2)} (fee GHS{" "}
                {Number(depositMutation.data.fee || 0).toFixed(2)}).
              </p>
            </div>
          ) : null}
        </section>

        <section className="card rounded-[28px] p-6">
          <h3 className="text-xl font-bold">Withdraw to bank or mobile money</h3>
          <p className="mt-2 text-sm leading-6 text-stone-600">
            Withdrawal charges apply only when money leaves the verified Avok account to MoMo or bank rails. Fee is 1% capped at GHS 30.
          </p>
          <form
            className="mt-5 space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              withdrawMutation.mutate(withdrawal);
            }}
          >
            <input
              className="field"
              value={withdrawal.amount}
              onChange={(event) => setWithdrawal((prev) => ({ ...prev, amount: event.target.value }))}
              placeholder="Amount"
            />
            <select
              className="field"
              value={withdrawal.destination_type}
              onChange={(event) => setWithdrawal((prev) => ({ ...prev, destination_type: event.target.value }))}
            >
              <option value="momo">Mobile money</option>
              <option value="bank">Bank</option>
            </select>
            <input
              className="field"
              value={withdrawal.destination_reference}
              onChange={(event) => setWithdrawal((prev) => ({ ...prev, destination_reference: event.target.value }))}
              placeholder={withdrawal.destination_type === "momo" ? "Mobile money number" : "Bank account or reference"}
            />
            {withdrawal.destination_type === "momo" ? (
              <select
                className="field"
                value={withdrawal.momo_provider}
                onChange={(event) => setWithdrawal((prev) => ({ ...prev, momo_provider: event.target.value }))}
              >
                <option value="mtn">MTN</option>
                <option value="telecel">Telecel</option>
                <option value="airtel_tigo">AirtelTigo</option>
              </select>
            ) : (
              <input
                className="field"
                value={withdrawal.bank_name}
                onChange={(event) => setWithdrawal((prev) => ({ ...prev, bank_name: event.target.value }))}
                placeholder="Bank name"
              />
            )}
            <button className="btn-primary w-full" type="submit">
              {withdrawMutation.isPending ? "Submitting..." : "Request withdrawal"}
            </button>
          </form>
          <div className="mt-4 rounded-[20px] bg-stone-50 px-4 py-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-stone-600">Withdrawal fee</span>
              <span className="font-bold">{formatGhs(withdrawalFee)}</span>
            </div>
            <div className="mt-2 flex items-center justify-between">
              <span className="text-stone-600">Net payout</span>
              <span className="font-bold">{formatGhs(withdrawalNet)}</span>
            </div>
          </div>
          {withdrawMutation.isSuccess ? (
            <pre className="mt-4 overflow-auto rounded-[22px] bg-stone-950 p-4 text-xs text-emerald-200">
              {JSON.stringify(withdrawMutation.data, null, 2)}
            </pre>
          ) : null}
          {withdrawMutation.isError ? (
            <p className="mt-4 rounded-2xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">{withdrawMutation.error.message}</p>
          ) : null}
        </section>
      </div>

      <section className="card rounded-[28px] p-6">
        <h3 className="text-xl font-bold">Transaction history</h3>
        <div className="mt-4 space-y-3">
          {allTransactions.length === 0 && !transactionsQuery.isLoading ? (
            <div className="rounded-[22px] bg-stone-50 p-5 text-sm text-stone-600">
              No transactions yet. Once you test deposit, payment hold, escrow release, refund, or withdrawal, they will appear here.
            </div>
          ) : (
            <>
              {allTransactions.map((transaction) => (
                <article key={transaction.reference} className="rounded-[22px] bg-stone-50 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="font-bold">{transaction.reference}</p>
                      <p className="mt-1 text-sm text-stone-600">{transaction.description || transaction.type}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.18em] text-stone-500">
                        {String(transaction.type || "").replaceAll("_", " ")} • {String(transaction.status || "").replaceAll("_", " ")}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="font-bold">{formatGhs(transaction.amount)}</p>
                      <p className="text-sm text-stone-500">Fee: {formatGhs(transaction.fee || 0)}</p>
                      <p className="text-sm text-stone-500">Net: {formatGhs(transaction.net_amount || 0)}</p>
                    </div>
                  </div>
                </article>
              ))}

              {hasMoreTransactions ? (
                <button
                  className="btn-secondary w-full py-4 text-stone-700"
                  onClick={() => setTransactionPage((prev) => prev + 1)}
                  disabled={transactionsQuery.isLoading}
                >
                  {transactionsQuery.isLoading ? "Loading more..." : "Load more transactions"}
                </button>
              ) : allTransactions.length > 0 ? (
                <p className="py-4 text-center text-sm text-stone-500">End of transaction history.</p>
              ) : null}
            </>
          )}
        </div>
      </section>
    </div>
  );
}
