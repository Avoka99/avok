"use client";

import { useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { api } from "@/lib/api";

export default function SuperAdminPage() {
  const user = useAuthStore(state => state.user);
  const [adminPhone, setAdminPhone] = useState("");
  const canAccess = Boolean(user && (user.role === "super_admin" || user.is_superuser));

  if (!canAccess) {
      return <div className="p-10 text-center text-rose-600 font-bold">Unauthorized: This area requires Super Admin privileges.</div>;
  }

  return (
    <div className="space-y-5">
      <section className="card rounded-[28px] p-6">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Super Admin Hub</p>
        <h2 className="mt-3 text-3xl font-black">Centralized Platform Control</h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-stone-600">
          This portal is strictly segregated for Super Administrators. You can configure core features and manipulate standard Administrator assignments safely from here.
        </p>
      </section>

      <section className="card rounded-[28px] bg-rose-50 p-6 border border-rose-200 mt-4 xl:col-span-2">
        <h3 className="text-xl font-bold text-rose-900">Super Admin Zone: Role Management</h3>
        <p className="mt-2 text-sm text-rose-700">Appoint or dismiss standard administrators securely by phone number.</p>
        <div className="mt-4 flex flex-col sm:flex-row gap-3 max-w-2xl">
          <input 
            className="field flex-1" 
            placeholder="Target User Phone Number (e.g. 0241234567)" 
            value={adminPhone}
            onChange={(e) => setAdminPhone(e.target.value)}
          />
          <button 
            type="button" 
            className="btn-primary bg-emerald-700 hover:bg-emerald-800 focus:ring-emerald-600 text-white whitespace-nowrap" 
            onClick={async () => {
              try {
                await api.post("/auth/roles/appoint-admin", { phone_number: adminPhone });
                alert("Admin Appointed Successfully!");
                setAdminPhone("");
              } catch (e) {
                alert(e.response?.data?.detail || e.message);
              }
            }}
          >
            Appoint Admin
          </button>
          <button 
            type="button" 
            className="btn-primary bg-rose-700 hover:bg-rose-800 focus:ring-rose-600 text-white whitespace-nowrap" 
            onClick={async () => {
              try {
                await api.post("/auth/roles/dismiss-admin", { phone_number: adminPhone });
                alert("Admin Dismissed Successfully!");
                setAdminPhone("");
              } catch (e) {
                alert(e.response?.data?.detail || e.message);
              }
            }}
          >
            Dismiss Admin
          </button>
        </div>
      </section>
    </div>
  );
}
