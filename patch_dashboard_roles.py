import sys
import os

def patch_sidebar():
    filepath = 'c:/Users/User/Desktop/AvokProject/frontend/components/Sidebar.jsx'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Import
    if "useAuthStore" not in content:
        content = content.replace(
            'import { Bell, LayoutDashboard, ShieldAlert, ShoppingBag, Wallet, BadgeCheck } from "lucide-react";',
            'import { Bell, LayoutDashboard, ShieldAlert, ShoppingBag, Wallet, BadgeCheck, Shield } from "lucide-react";\nimport { useAuthStore } from "@/stores/auth-store";'
        )

    # Base items array update to add super-admin conceptually but filter later
    old_items = """const items = [
  { href: "/buyer", label: "Payer", icon: ShoppingBag },
  { href: "/seller", label: "Recipient", icon: LayoutDashboard },
  { href: "/admin", label: "Admin", icon: ShieldAlert },
  { href: "/account", label: "Verified Account", icon: BadgeCheck },
  { href: "/wallet", label: "Wallet", icon: Wallet },
  { href: "/notifications", label: "Alerts", icon: Bell }
];"""
    
    new_items = """const baseItems = [
  { href: "/buyer", label: "Payer", icon: ShoppingBag },
  { href: "/seller", label: "Recipient", icon: LayoutDashboard },
  { href: "/account", label: "Verify Account", icon: BadgeCheck },
  { href: "/wallet", label: "Wallet", icon: Wallet },
  { href: "/notifications", label: "Alerts", icon: Bell }
];

const adminItem = { href: "/admin", label: "Admin Portal", icon: ShieldAlert };
const superAdminItem = { href: "/super-admin", label: "Super Admin", icon: Shield };"""

    if old_items in content:
        content = content.replace(old_items, new_items)

    # Hooks and filtering
    old_component_start = """export default function Sidebar() {
  const pathname = usePathname();"""
    new_component_start = """export default function Sidebar() {
  const pathname = usePathname();
  const user = useAuthStore(state => state.user);
  
  const items = [...baseItems];
  if (user?.role === 'admin' || user?.role === 'super_admin' || user?.is_superuser) {
      items.splice(2, 0, adminItem); 
  }
  if (user?.role === 'super_admin' || user?.is_superuser) {
      items.push(superAdminItem);
  }
"""
    if old_component_start in content:
        content = content.replace(old_component_start, new_component_start)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def patch_account():
    filepath = 'c:/Users/User/Desktop/AvokProject/frontend/app/(dashboard)/account/page.jsx'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove Super Admin Widget
    start_str = "        {user?.role === 'super_admin' && ("
    end_str = "        )}\n      </div>"
    
    if start_str in content and end_str in content:
        start_idx = content.find(start_str)
        end_idx = content.find(end_str) + len("        )}\n      </div>")
        content = content[:start_idx] + "      </div>" + content[end_idx:]

    # Remove state
    state_str = '  const [adminPhone, setAdminPhone] = useState("");'
    if state_str in content:
        content = content.replace(state_str, "")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def patch_admin():
    filepath = 'c:/Users/User/Desktop/AvokProject/frontend/app/(dashboard)/admin/page.jsx'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Add useAuthStore
    if "useAuthStore" not in content:
        content = content.replace('import { api } from "@/lib/api";', 'import { api } from "@/lib/api";\nimport { useAuthStore } from "@/stores/auth-store";')

    # Add guard
    old_start = """export default function AdminDashboardPage() {
  const queryClient = useQueryClient();"""
    new_start = """export default function AdminDashboardPage() {
  const user = useAuthStore(state => state.user);
  const queryClient = useQueryClient();

  if (!user || (user.role !== 'admin' && user.role !== 'super_admin' && !user.is_superuser)) {
      return <div className="p-10 text-center text-rose-600 font-bold">Unauthorized: This area requires elevated privileges.</div>;
  }
"""
    if old_start in content:
        content = content.replace(old_start, new_start)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def create_super_admin():
    dirpath = 'c:/Users/User/Desktop/AvokProject/frontend/app/(dashboard)/super-admin'
    os.makedirs(dirpath, exist_ok=True)
    
    filepath = f'{dirpath}/page.jsx'
    content = """"use client";

import { useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { api } from "@/lib/api";

export default function SuperAdminPage() {
  const user = useAuthStore(state => state.user);
  const [adminPhone, setAdminPhone] = useState("");

  if (!user || (user.role !== 'super_admin' && !user.is_superuser)) {
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
"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    patch_sidebar()
    patch_account()
    patch_admin()
    create_super_admin()
    print("Patched Dashboard Roles Layouts.")
