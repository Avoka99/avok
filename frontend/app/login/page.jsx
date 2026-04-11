"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ShieldCheck, Eye, EyeOff } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { api } from "@/lib/api";

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginPageSkeleton />}>
      <LoginPageContent />
    </Suspense>
  );
}

function LoginPageContent() {
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
  const [showPassword, setShowPassword] = useState(false);
  const [showReset, setShowReset] = useState(false);
  const [resetForm, setResetForm] = useState({ phone_number: "", otp: "", new_password: "" });
  const [resetLoading, setResetLoading] = useState(false);
  const [resetSent, setResetSent] = useState(false);

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
        } catch { }
      }
      const role = tokenRole === "admin" || tokenRole === "super_admin" ? "admin" : data?.user?.role || tokenRole || "user";
      const target = role === "admin" ? "/admin" : role === "super_admin" ? "/super-admin" : "/buyer";
      router.push(target);
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleResetRequest(event) {
    event.preventDefault();
    setResetLoading(true);
    setError("");
    try {
      await api.post("/auth/password-reset/request", null, { params: { phone_number: resetForm.phone_number } });
      setResetSent(true);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Failed to send reset code");
    } finally {
      setResetLoading(false);
    }
  }

  async function handleResetConfirm(event) {
    event.preventDefault();
    setResetLoading(true);
    setError("");
    try {
      await api.post("/auth/password-reset/confirm", null, {
        params: {
          phone_number: resetForm.phone_number,
          otp: resetForm.otp,
          new_password: resetForm.new_password,
        },
      });
      setShowReset(false);
      setResetSent(false);
      setResetForm({ phone_number: "", otp: "", new_password: "" });
      setError("Password reset successfully. Please log in with your new password.");
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Failed to reset password");
    } finally {
      setResetLoading(false);
    }
  }

  if (showReset) {
    return (
      <main className="page-shell flex items-center justify-center">
        <div className="card rounded-[30px] p-6 sm:p-8 w-full max-w-md">
          <h2 className="text-2xl font-black">Reset Password</h2>
          <p className="mt-2 text-sm text-stone-600">
            {!resetSent
              ? "Enter your phone number to receive a reset code."
              : "Enter the code from your phone and your new password."}
          </p>

          <form onSubmit={!resetSent ? handleResetRequest : handleResetConfirm} className="mt-6 space-y-4">
            <div>
              <label className="mb-2 block text-sm font-semibold text-stone-700">Phone number</label>
              <input
                className="field"
                value={resetForm.phone_number}
                onChange={(e) => setResetForm((p) => ({ ...p, phone_number: e.target.value }))}
                placeholder="0241111111"
                disabled={resetSent}
                required
              />
            </div>

            {resetSent && (
              <>
                <div>
                  <label className="mb-2 block text-sm font-semibold text-stone-700">Reset code</label>
                  <input
                    className="field"
                    value={resetForm.otp}
                    onChange={(e) => setResetForm((p) => ({ ...p, otp: e.target.value }))}
                    placeholder="123456"
                    maxLength={6}
                    required
                  />
                </div>
                <div>
                  <label className="mb-2 block text-sm font-semibold text-stone-700">New password</label>
                  <input
                    type="password"
                    className="field"
                    value={resetForm.new_password}
                    onChange={(e) => setResetForm((p) => ({ ...p, new_password: e.target.value }))}
                    placeholder="Enter new password"
                    required
                    minLength={8}
                  />
                </div>
              </>
            )}

            {error && (
              <p className={`rounded-2xl px-4 py-3 text-sm font-medium ${error.includes("successfully") ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
                }`}>{error}</p>
            )}

            <button type="submit" className="btn-primary w-full" disabled={resetLoading}>
              {resetLoading ? "Processing..." : resetSent ? "Reset Password" : "Send Reset Code"}
            </button>
          </form>

          <button
            type="button"
            onClick={() => { setShowReset(false); setResetSent(false); setResetForm({ phone_number: "", otp: "", new_password: "" }); setError(""); }}
            className="mt-4 w-full text-center text-sm font-semibold text-emerald-700 hover:text-emerald-800"
          >
            Back to login
          </button>
        </div>
      </main>
    );
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
                required
              />
            </div>
            <div>
              <label className="mb-2 block text-sm font-semibold text-stone-700">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  className="field pr-12"
                  value={form.password}
                  onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
                  placeholder="Enter your password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            {error ? <p className="rounded-2xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-700">{error}</p> : null}
            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? "Signing in..." : "Login securely"}
            </button>
          </form>

          <div className="mt-4 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setShowReset(true)}
              className="text-sm font-semibold text-emerald-700 hover:text-emerald-800"
            >
              Forgot password?
            </button>
            <p className="text-sm text-stone-600">
              New to Avok?{" "}
              <Link href="/register" className="font-bold text-emerald-700">
                Create an account
              </Link>
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}

function LoginPageSkeleton() {
  return (
    <main className="page-shell flex items-center justify-center">
      <div className="card rounded-[30px] p-8 text-sm text-stone-600">Loading secure sign-in...</div>
    </main>
  );
}
