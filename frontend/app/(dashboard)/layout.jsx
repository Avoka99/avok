"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import Topbar from "@/components/Topbar";
import { useAuthStore } from "@/stores/auth-store";

export default function DashboardLayout({ children }) {
  const router = useRouter();
  const pathname = usePathname();
  const accessToken = useAuthStore((state) => state.accessToken);
  const hydrated = useAuthStore((state) => state.hydrated);
  const allowGuestCheckout = pathname === "/checkout/new" || pathname === "/payments";

  useEffect(() => {
    if (hydrated && !accessToken && !allowGuestCheckout) {
      router.replace("/login");
    }
  }, [hydrated, accessToken, allowGuestCheckout, router]);

  if (!hydrated) {
    return (
      <main className="page-shell flex items-center justify-center">
        <div className="card rounded-[28px] p-6 text-center">
          <h1 className="text-2xl font-black">Loading secure session</h1>
          <p className="mt-2 text-sm text-stone-600">Avok is preparing your checkout experience.</p>
        </div>
      </main>
    );
  }

  if (!accessToken && allowGuestCheckout) {
    return <main className="page-shell">{children}</main>;
  }

  if (!accessToken) {
    return (
      <main className="page-shell flex items-center justify-center">
        <div className="card rounded-[28px] p-6 text-center">
          <h1 className="text-2xl font-black">Sign in to continue</h1>
          <p className="mt-2 text-sm text-stone-600">Avok needs an active session before it can create checkout sessions or load wallet data.</p>
        </div>
      </main>
    );
  }

  return (
    <main className="page-shell">
      <div className="mx-auto flex max-w-7xl gap-4">
        <Sidebar />
        <div className="flex min-h-[calc(100vh-2rem)] flex-1 flex-col gap-4">
          <Topbar />
          <div className="flex-1">{children}</div>
        </div>
      </div>
    </main>
  );
}
