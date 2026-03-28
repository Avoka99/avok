import sys
import re

def patch_register():
    filepath = 'c:/Users/User/Desktop/AvokProject/frontend/app/register/page.jsx'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove roles array
    roles_str = """const roles = [
  { value: "buyer", label: "Payer" },
  { value: "seller", label: "Recipient" }
];"""
    content = content.replace(roles_str, "")

    # Update form state
    old_state = """    email: "",
    password: "",
    role: "buyer"
  });"""
    new_state = """    email: "",
    password: "",
    wants_avok_account: true
  });"""
    content = content.replace(old_state, new_state)

    # Replace Account type dropdown
    old_select = """          <div>
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
          </div>"""
          
    new_select = """          <div className="sm:col-span-2 card rounded-[24px] bg-stone-50 p-5 border border-stone-200">
            <label className="mb-2 block text-sm font-semibold text-stone-700">Would you like an Avok account number to hold money for transactions?</label>
            <p className="text-sm text-stone-500 mb-4">You can get one now or opt-in later from your dashboard.</p>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input 
                  type="radio" 
                  name="wants_avok_account"
                  checked={form.wants_avok_account === true}
                  onChange={() => setForm(prev => ({ ...prev, wants_avok_account: true }))}
                  className="w-5 h-5 text-emerald-600 focus:ring-emerald-500"
                />
                <span className="font-medium text-stone-800">Yes, allocate an account</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input 
                  type="radio" 
                  name="wants_avok_account"
                  checked={form.wants_avok_account === false}
                  onChange={() => setForm(prev => ({ ...prev, wants_avok_account: false }))}
                  className="w-5 h-5 text-stone-600 focus:ring-stone-500"
                />
                <span className="font-medium text-stone-800">No, maybe later</span>
              </label>
            </div>
          </div>"""
          
    content = content.replace(old_select, new_select)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def patch_account():
    filepath = 'c:/Users/User/Desktop/AvokProject/frontend/app/(dashboard)/account/page.jsx'
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Imports
    if "useAuthStore" not in content:
        content = content.replace('import { useState } from "react";', 'import { useState, useEffect } from "react";\nimport { useAuthStore } from "@/stores/auth-store";\nimport { api } from "@/lib/api";')

    # Component setup
    old_comp_start = """export default function VerifiedAccountPage() {
  const [profile, setProfile] = useState({
    full_name: "",
    phone_number: "",
    ghana_card_number: "",
    bank_or_momo_target: "",
    otp: ""
  });"""
  
    new_comp_start = """export default function VerifiedAccountPage() {
  const user = useAuthStore(state => state.user);
  const setUser = useAuthStore(state => state.setUser);
  const [allocating, setAllocating] = useState(false);
  
  const [profile, setProfile] = useState({
    full_name: user?.full_name || "",
    phone_number: user?.phone_number || "",
    ghana_card_number: "",
    bank_or_momo_target: "",
    otp: "",
    avok_account_number: user?.avok_account_number || ""
  });

  useEffect(() => {
    if (user) {
      setProfile(prev => ({ 
        ...prev, 
        full_name: user.full_name || "", 
        phone_number: user.phone_number || "",
        avok_account_number: user.avok_account_number || ""
      }));
    }
  }, [user]);

  const handleAllocateAccount = async () => {
    try {
      setAllocating(true);
      const { data } = await api.post("/auth/allocate-account");
      setUser(data);
      alert("Account allocated successfully!");
    } catch (e) {
      alert("Could not allocate account: " + e.message);
    } finally {
      setAllocating(false);
    }
  };"""

    content = content.replace(old_comp_start, new_comp_start)

    # Form fields
    old_fields = """          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <input
              className="field"
              placeholder="Full name"
              value={profile.full_name}"""
              
    new_fields = """          {user && !user.avok_account_number ? (
            <div className="mt-5 mb-5 rounded-[20px] bg-emerald-50 p-5 sm:col-span-2 text-center">
              <p className="text-emerald-800 font-medium mb-3">You don't have an Avok account number yet.</p>
              <button 
                type="button" 
                onClick={handleAllocateAccount} 
                disabled={allocating}
                className="btn-primary"
              >
                {allocating ? "Allocating..." : "Get Avok Account Number"}
              </button>
            </div>
          ) : null}
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <input
              className="field"
              placeholder="Avok Account Number"
              value={profile.avok_account_number}
              readOnly
              style={{ backgroundColor: "#f3f4f6", opacity: 0.8 }}
            />
            <input
              className="field"
              placeholder="Full name"
              value={profile.full_name}"""
              
    content = content.replace(old_fields, new_fields)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    patch_register()
    patch_account()
    print("Patched React frontend.")
