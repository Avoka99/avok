"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionNotice =
    searchParams.get("reason") === "session"
      ? "Your session ended or your sign-in is no longer valid. Please log in again."
      : "";
  const login = useAuthStore((state) => state.login);
  const [form, setForm] = useState({ phone_number: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      const data = await login(form);
      const accessToken = data?.access_token || data?.token || null;
      let tokenRole = null;
      if (accessToken) {
        try {
          const payload = JSON.parse(atob(accessToken.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
          tokenRole = payload?.role || null;
        } catch {}
      }
      const role = tokenRole === "admin" || tokenRole === "super_admin" ? "admin" : data?.user?.role || tokenRole || "buyer";
      const target = role === "seller" ? "/seller" : role === "admin" ? "/admin" : "/buyer";
      router.push(target);
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-shell flex items-center justify-center">
      <div className="grid w-full max-w-5xl gap-5 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="card rounded-[30px] bg-emerald-950 p-8 text-white">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-2 text-sm font-semibold">
            <ShieldCheck className="h-4 w-4" />
            Trust-first payment protection
          </div>
          <h1 className="mt-8 text-4xl font-black leading-tight">Login to view your orders, wallet, and escrow progress.</h1>
          <p className="mt-4 max-w-lg text-sm leading-7 text-emerald-50">
            Payers, recipients, and admins all get clear visibility into where the money is, what has happened, and what action comes next.
          </p>
        </section>

        <section className="card rounded-[30px] p-6 sm:p-8">
          <h2 className="text-3xl font-black">Welcome back</h2>
          <p className="mt-2 text-sm text-stone-600">Use your phone number and password to access your dashboard.</p>
          {sessionNotice ? (
            <p className="mt-4 rounded-2xl bg-amber-50 px-4 py-3 text-sm font-medium text-amber-900">{sessionNotice}</p>
          ) : null}

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label className="mb-2 block text-sm font-semibold text-stone-700">Phone number</label>
              <input
                className="field"
                value={form.phone_number}
                onChange={(event) => setForm((prev) => ({ ...prev, phone_number: event.target.value }))}
                placeholder="0241111111"
              />
            </div>
            <div>
              <label className="mb-2 block text-sm font-semibold text-stone-700">Password</label>
              <input
                type="password"
                className="field"
                value={form.password}
                onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
                placeholder="Enter your password"
              />
            </div>
            {error ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">{error}</p> : null}
            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? "Signing in..." : "Login securely"}
            </button>
          </form>

          <p className="mt-5 text-sm text-stone-600">
            New to Avok?{" "}
            <Link href="/register" className="font-bold text-emerald-700">
              Create an account
            </Link>
          </p>
        </section>
      </div>
    </main>
  );
}
