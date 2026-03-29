"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { api } from "@/lib/api";

export default function VerifiedAccountPage() {
  const user = useAuthStore(state => state.user);
  const setUser = useAuthStore(state => state.setUser);
  const [allocating, setAllocating] = useState(false);

  
  const [profile, setProfile] = useState({
    full_name: user?.full_name || "",
    phone_number: user?.phone_number || "",
    document_type: "ghana_card",
    document_number: "",
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
    if (user?.avok_account_number) {
      alert("You already have an Avok account number: " + user.avok_account_number);
      return;
    }
    try {
      setAllocating(true);
      const { data } = await api.post("/auth/allocate-account");
      setUser(data);
      alert("Account allocated successfully!\nYour Avok Account: " + data.avok_account_number);
    } catch (e) {
      alert("Could not allocate account: " + e.message);
    } finally {
      setAllocating(false);
    }
  };

  return (
    <div className="space-y-5">
      <section className="card rounded-[28px] p-6">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Verify Account</p>
        <h2 className="mt-3 text-3xl font-black">One verified account can hold deposits and escrow releases for payment use.</h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-stone-600">
          Users who complete signup and verification get an Avok payment account. Money can enter it from deposit or from escrow release, and spending from this verified balance for purchases should not attract extra fees.
        </p>
        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <div className="rounded-[22px] bg-stone-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500">Current phone status</p>
            <p className="mt-2 text-sm font-bold text-stone-900">{user?.is_phone_verified ? "Verified" : "Still needed"}</p>
            <p className="mt-2 text-sm text-stone-600">Phone verification is mainly for larger checkouts and urgent account recovery.</p>
          </div>
          <div className="rounded-[22px] bg-stone-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-stone-500">Current KYC status</p>
            <p className="mt-2 text-sm font-bold text-stone-900">{user?.kyc_status ? String(user.kyc_status).replaceAll("_", " ") : "Not started"}</p>
            <p className="mt-2 text-sm text-stone-600">Full KYC is mostly for stored balance, withdrawals, and higher-risk payment review.</p>
          </div>
          <div className="rounded-[22px] bg-emerald-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-700">Why this matters</p>
            <p className="mt-2 text-sm font-bold text-emerald-900">Low-risk checkout stays fast</p>
            <p className="mt-2 text-sm text-emerald-800">Avok should only ask for stronger checks when the payment method or amount makes it necessary.</p>
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <section className="card rounded-[28px] p-6">
          <h3 className="text-xl font-bold">Verification checklist</h3>
          {user && !user.avok_account_number ? (
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
            <div>
              <input
                className="field"
                placeholder="Avok Account Number"
                value={profile.avok_account_number}
                readOnly
                style={{ backgroundColor: "#f3f4f6", opacity: 0.8 }}
              />
              <p className="text-xs text-stone-500 mt-1">Your Avok payment account</p>
            </div>
            <input
              className="field"
              placeholder="Full name"
              value={profile.full_name}
              onChange={(event) => setProfile((prev) => ({ ...prev, full_name: event.target.value }))}
            />
            <input
              className="field"
              placeholder="Phone number"
              value={profile.phone_number}
              onChange={(event) => setProfile((prev) => ({ ...prev, phone_number: event.target.value }))}
            />
            <select
              className="field"
              value={profile.document_type}
              onChange={(event) => setProfile((prev) => ({ ...prev, document_type: event.target.value }))}
            >
              <option value="ghana_card">Ghana Card</option>
              <option value="voter_id">Voter ID</option>
              <option value="driver_license">Driver License</option>
              <option value="national_id">Other National ID</option>
            </select>
            <input
              className="field"
              placeholder="Document Number *"
              value={profile.document_number}
              onChange={(event) => setProfile((prev) => ({ ...prev, document_number: event.target.value }))}
            />
            <input
              className="field"
              placeholder="Preferred bank or MoMo destination"
              value={profile.bank_or_momo_target}
              onChange={(event) => setProfile((prev) => ({ ...prev, bank_or_momo_target: event.target.value }))}
            />
            <div className="sm:col-span-2">
              <label className="block text-sm font-medium text-stone-700 mb-1">Document Image *</label>
              <input type="file" className="field" />
            </div>
            <div className="sm:col-span-2">
              <label className="block text-sm font-medium text-stone-700 mb-1">Selfie Image *</label>
              <input type="file" className="field" />
            </div>
            <input
              className="field"
              placeholder="Phone OTP"
              value={profile.otp}
              onChange={(event) => setProfile((prev) => ({ ...prev, otp: event.target.value }))}
            />
          </div>
          <p className="text-xs text-stone-500 mt-2">* Required fields must be filled before submission</p>
          <button type="button" className="btn-primary mt-5 w-full" onClick={async () => {
              if (!profile.document_number) {
                alert("Please fill in all required fields:\n- Document Number\n- Document Image\n- Selfie Image");
                return;
              }
              try {
                  await api.post("/auth/kyc", {
                      document_type: profile.document_type,
                      document_number: profile.document_number,
                      document_image: "dummy_image_url",
                      selfie_image: "dummy_selfie_url"
                  });
                  
                  // Refresh user data to get latest status
                  const { data: userData } = await api.get("/auth/me");
                  setUser(userData);
                  
                  alert("KYC Submitted Successfully!\nYour Avok Account: " + userData.avok_account_number + "\n\nAdmins will review your verification.");
              } catch(e) {
                  alert(e.response?.data?.detail || e.message);
              }
          }}>
            Submit verification details
          </button>
        </section>

        <section className="card rounded-[28px] bg-stone-900 p-6 text-white">
          <h3 className="text-xl font-bold">Verification and fee rules</h3>
          <div className="mt-5 space-y-3">
            <div className="rounded-[22px] bg-white/10 p-4">
              <p className="font-semibold">Low-risk checkout by MoMo or bank</p>
              <p className="mt-2 text-sm text-stone-200">Usually the fastest path. Avok may only ask for basic contact details so funds and updates reach you.</p>
            </div>
            <div className="rounded-[22px] bg-white/10 p-4">
              <p className="font-semibold">Larger checkout amounts</p>
              <p className="mt-2 text-sm text-stone-200">Phone verification helps Avok confirm the payer quickly before higher-value money moves.</p>
            </div>
            <div className="rounded-[22px] bg-white/10 p-4">
              <p className="font-semibold">Deposit from MoMo or bank into Avok balance</p>
              <p className="mt-2 text-sm text-stone-200">1% fee, capped at GHS 30.</p>
            </div>
            <div className="rounded-[22px] bg-white/10 p-4">
              <p className="font-semibold">Withdrawal to MoMo or bank</p>
              <p className="mt-2 text-sm text-stone-200">1% fee, capped at GHS 30.</p>
            </div>
            <div className="rounded-[22px] bg-white/10 p-4">
              <p className="font-semibold">Use verified balance to pay for purchases</p>
              <p className="mt-2 text-sm text-stone-200">No fee, but this is the strictest path because it requires phone verification and approved KYC.</p>
            </div>
            <div className="rounded-[22px] bg-emerald-900/70 p-4 text-sm leading-6 text-emerald-50">
              Escrow releases into a verified Avok account should arrive without extra release charge. Charges only apply when funds move in or out through MoMo or bank rails.
            </div>
          </div>
        </section>

      </div>
    </div>
  );
}
