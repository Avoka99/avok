"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";

const roles = [
  { value: "buyer", label: "Payer" },
  { value: "seller", label: "Recipient" }
];

export default function RegisterPage() {
  const router = useRouter();
  const register = useAuthStore((state) => state.register);
  const [form, setForm] = useState({
    full_name: "",
    phone_number: "",
    email: "",
    password: "",
    role: "buyer"
  });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setMessage("");

    try {
      await register(form);
      setMessage("Account created. Continue to login and test the user flow.");
      setTimeout(() => router.push("/login"), 900);
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-shell flex items-center justify-center">
      <div className="card w-full max-w-3xl rounded-[30px] p-6 sm:p-8">
        <h1 className="text-3xl font-black">Create a secure Avok account</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-stone-600">
          Choose whether you are buying or selling. You can later test KYC upload, phone verification, wallet funding, and the escrow order flow.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="mb-2 block text-sm font-semibold text-stone-700">Full name</label>
            <input
              className="field"
              value={form.full_name}
              onChange={(event) => setForm((prev) => ({ ...prev, full_name: event.target.value }))}
              placeholder="Kwame Mensah"
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-semibold text-stone-700">Phone number</label>
            <input
              className="field"
              value={form.phone_number}
              onChange={(event) => setForm((prev) => ({ ...prev, phone_number: event.target.value }))}
              placeholder="0241234567"
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-semibold text-stone-700">Email</label>
            <input
              type="email"
              className="field"
              value={form.email}
              onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-semibold text-stone-700">Password</label>
            <input
              type="password"
              className="field"
              value={form.password}
              onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
              placeholder="Create a password"
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-semibold text-stone-700">Account type</label>
            <select
              className="field"
              value={form.role}
              onChange={(event) => setForm((prev) => ({ ...prev, role: event.target.value }))}
            >
              {roles.map((role) => (
                <option key={role.value} value={role.value}>
                  {role.label}
                </option>
              ))}
            </select>
          </div>

          <div className="card rounded-[24px] bg-stone-50 p-5 sm:col-span-2">
            <h2 className="text-lg font-bold">KYC and phone verification</h2>
            <p className="mt-2 text-sm leading-6 text-stone-600">
              This frontend is ready for ID upload and OTP steps. The UI keeps them visible so users understand why trust checks matter before money moves.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <input type="file" className="field" />
              <input className="field" placeholder="Enter OTP when sent" />
            </div>
          </div>

          {message ? <p className="rounded-2xl bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700 sm:col-span-2">{message}</p> : null}
          {error ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700 sm:col-span-2">{error}</p> : null}

          <button type="submit" className="btn-primary sm:col-span-2" disabled={loading}>
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>

        <p className="mt-5 text-sm text-stone-600">
          Already registered?{" "}
          <Link href="/login" className="font-bold text-emerald-700">
            Go to login
          </Link>
        </p>
      </div>
    </main>
  );
}
