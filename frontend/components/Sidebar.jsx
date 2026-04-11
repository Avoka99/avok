"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, LayoutDashboard, ShieldAlert, ShoppingBag, Wallet, BadgeCheck, Shield } from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";

const baseItems = [
  { href: "/buyer", label: "My Payments", icon: ShoppingBag },
  { href: "/seller", label: "My Receipts", icon: LayoutDashboard },
  { href: "/account", label: "Verify Account", icon: BadgeCheck },
  { href: "/wallet", label: "Wallet", icon: Wallet },
  { href: "/notifications", label: "Alerts", icon: Bell }
];

const adminItem = { href: "/admin", label: "Admin Portal", icon: ShieldAlert };
const superAdminItem = { href: "/super-admin", label: "Super Admin", icon: Shield };

export default function Sidebar() {
  const pathname = usePathname();
  const user = useAuthStore(state => state.user);
  
  const items = [...baseItems];
  if (user?.role === 'admin' || user?.role === 'super_admin' || user?.is_superuser) {
      items.splice(2, 0, adminItem); 
  }
  if (user?.role === 'super_admin' || user?.is_superuser) {
      items.push(superAdminItem);
  }


  return (
    <aside className="card hidden w-72 shrink-0 rounded-[28px] p-4 lg:block">
      <div className="rounded-[24px] bg-emerald-900 px-5 py-6 text-white">
        <p className="text-sm uppercase tracking-[0.2em] text-emerald-100">Avok</p>
        <h2 className="mt-3 text-2xl font-black">Escrow operations</h2>
        <p className="mt-2 text-sm leading-6 text-emerald-50">Track funds, verify payments, and keep checkout decisions easy to follow.</p>
      </div>

      <nav className="mt-4 space-y-2" role="navigation" aria-label="Dashboard navigation">
        {items.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-semibold transition ${
                active ? "bg-emerald-50 text-emerald-800" : "text-stone-600 hover:bg-stone-50"
              }`}
              aria-current={active ? "page" : undefined}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
