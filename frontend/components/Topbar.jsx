"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Menu, ShieldCheck, User } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { useState } from "react";

export default function Topbar({ onToggleMobileMenu }) {
  const router = useRouter();
  const { user, logout } = useAuthStore();
  const [showProfile, setShowProfile] = useState(false);

  function handleLogout() {
    logout();
    router.push("/login");
  }

  const userRole = user?.role?.toLowerCase() || "user";
  const isAdmin = userRole === "admin";
  const isSuperAdmin = userRole === "super_admin";

  return (
    <header className="card glass flex items-center justify-between rounded-[24px] px-4 py-3">
      <div className="flex items-center gap-3">
        <button className="rounded-2xl bg-stone-100 p-3 text-stone-700 lg:hidden" type="button" onClick={onToggleMobileMenu} aria-label="Open navigation menu">
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

        {/* Profile dropdown */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowProfile(!showProfile)}
            className="flex items-center gap-2 rounded-full bg-stone-100 px-3 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-200 transition"
            aria-label="User profile menu"
            aria-expanded={showProfile}
          >
            <User className="h-4 w-4" />
            <span className="hidden sm:inline">{user?.phone_number || "Guest"}</span>
            {isSuperAdmin && (
              <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.1em] text-red-700">Super Admin</span>
            )}
            {isAdmin && !isSuperAdmin && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.1em] text-amber-700">Admin</span>
            )}
          </button>

          {showProfile && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowProfile(false)} />
              <div className="absolute right-0 z-50 mt-2 w-72 rounded-[20px] bg-white p-5 shadow-xl border border-stone-200">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
                    <span className="text-sm font-bold text-emerald-800">
                      {(user?.full_name || user?.phone_number || "U").charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-bold text-stone-900">{user?.full_name || "User"}</p>
                    <p className="truncate text-xs text-stone-500">{user?.phone_number}</p>
                    {user?.email && <p className="truncate text-xs text-stone-500">{user.email}</p>}
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-1">
                  {isSuperAdmin && (
                    <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.1em] text-red-700">Super Admin</span>
                  )}
                  {isAdmin && !isSuperAdmin && (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.1em] text-amber-700">Admin</span>
                  )}
                  {!isAdmin && !isSuperAdmin && (
                    <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.1em] text-stone-600">User</span>
                  )}
                </div>

                <div className="mt-4 space-y-2">
                  <Link
                    href="/account"
                    className="block w-full text-center text-sm font-semibold text-emerald-700 hover:text-emerald-800 py-2 rounded-xl hover:bg-emerald-50 transition"
                    onClick={() => setShowProfile(false)}
                  >
                    View Profile
                  </Link>
                  <button
                    type="button"
                    onClick={() => { setShowProfile(false); handleLogout(); }}
                    className="block w-full text-center text-sm font-semibold text-rose-600 hover:text-rose-700 py-2 rounded-xl hover:bg-rose-50 transition"
                  >
                    Logout
                  </button>
                </div>
              </div>
            </>
          )}
        </div>

        <button type="button" onClick={handleLogout} className="btn-secondary text-sm hidden sm:inline-flex">
          Logout
        </button>
      </div>
    </header>
  );
}
