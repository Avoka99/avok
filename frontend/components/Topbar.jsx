"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Menu, ShieldCheck } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";

export default function Topbar() {
  const router = useRouter();
  const { user, logout } = useAuthStore();

  function handleLogout() {
    logout();
    router.push("/login");
  }

  return (
    <header className="card glass flex items-center justify-between rounded-[24px] px-4 py-3">
      <div className="flex items-center gap-3">
        <button className="rounded-2xl bg-stone-100 p-3 text-stone-700 lg:hidden" type="button">
          <Menu className="h-4 w-4" />
        </button>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-500">Safety first</p>
          <h1 className="text-lg font-bold text-stone-900">Avok dashboard</h1>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden items-center gap-2 rounded-full bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-800 sm:flex">
          <ShieldCheck className="h-4 w-4" />
          Funds tracked in escrow
        </div>
        <Link href="/login" className="text-sm font-semibold text-stone-500">
          {user?.phone_number || "Guest"}
        </Link>
        <button type="button" onClick={handleLogout} className="btn-secondary text-sm">
          Logout
        </button>
      </div>
    </header>
  );
}
