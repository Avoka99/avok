"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import Topbar from "@/components/Topbar";
import { ToastProvider } from "@/components/Toast";
import { useAuthStore } from "@/stores/auth-store";

export default function DashboardLayout({ children }) {
  const router = useRouter();
  const pathname = usePathname();
  const accessToken = useAuthStore((state) => state.accessToken);
  const hydrated = useAuthStore((state) => state.hydrated);
  const allowGuestCheckout = pathname === "/checkout/new" || pathname === "/payments";
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    if (hydrated && !accessToken && !allowGuestCheckout) {
      router.replace("/login");
    }
  }, [hydrated, accessToken, allowGuestCheckout, router]);

  if (!hydrated) {
    return (
      <main className="page-shell flex items-center justify-center">
        <div className="card rounded-[28px] p-6 text-center" role="status" aria-live="polite">
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
        <div className="card rounded-[28px] p-6 text-center" role="status" aria-live="polite">
          <h1 className="text-2xl font-black">Sign in to continue</h1>
          <p className="mt-2 text-sm text-stone-600">Avok needs an active session before it can create checkout sessions or load wallet data.</p>
        </div>
      </main>
    );
  }

  return (
    <ToastProvider>
      <main className="page-shell">
        {/* Mobile sidebar overlay */}
        {mobileMenuOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/50 lg:hidden"
            onClick={() => setMobileMenuOpen(false)}
            role="dialog"
            aria-modal="true"
            aria-label="Mobile navigation overlay"
          />
        )}
        {/* Mobile sidebar */}
        <div className={`fixed inset-y-0 left-0 z-50 w-72 transform transition-transform duration-300 lg:hidden ${
          mobileMenuOpen ? "translate-x-0" : "-translate-x-full"
        }`} role="dialog" aria-modal="true" aria-label="Mobile navigation menu">
          <div className="flex h-full flex-col bg-white p-4">
            <div className="flex justify-end">
              <button
                type="button"
                className="rounded-xl bg-stone-100 p-2 text-stone-700"
                onClick={() => setMobileMenuOpen(false)}
                aria-label="Close navigation menu"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="mt-4 flex-1 overflow-y-auto">
              <Sidebar />
            </div>
          </div>
        </div>

        <div className="mx-auto flex max-w-7xl gap-4">
          <Sidebar />
          <div className="flex min-h-[calc(100vh-2rem)] flex-1 flex-col gap-4">
            <Topbar onToggleMobileMenu={() => setMobileMenuOpen(!mobileMenuOpen)} />
            <div className="flex-1">{children}</div>
          </div>
        </div>
      </main>
    </ToastProvider>
  );
}
