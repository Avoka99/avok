"use client";

import { useState } from "react";

export default function VerifiedAccountPage() {
  const [profile, setProfile] = useState({
    full_name: "",
    phone_number: "",
    ghana_card_number: "",
    bank_or_momo_target: "",
    otp: ""
  });

  return (
    <div className="space-y-5">
      <section className="card rounded-[28px] p-6">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Verified Avok account</p>
        <h2 className="mt-3 text-3xl font-black">One verified account can hold deposits and escrow releases for payment use.</h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-stone-600">
          Users who complete signup and verification get an Avok payment account. Money can enter it from deposit or from escrow release, and spending from this verified balance for purchases should not attract extra fees.
        </p>
      </section>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <section className="card rounded-[28px] p-6">
          <h3 className="text-xl font-bold">Verification checklist</h3>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
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
            <input
              className="field"
              placeholder="Ghana Card number"
              value={profile.ghana_card_number}
              onChange={(event) => setProfile((prev) => ({ ...prev, ghana_card_number: event.target.value }))}
            />
            <input
              className="field"
              placeholder="Preferred bank or MoMo destination"
              value={profile.bank_or_momo_target}
              onChange={(event) => setProfile((prev) => ({ ...prev, bank_or_momo_target: event.target.value }))}
            />
            <div className="sm:col-span-2">
              <input type="file" className="field" />
            </div>
            <input
              className="field"
              placeholder="Phone OTP"
              value={profile.otp}
              onChange={(event) => setProfile((prev) => ({ ...prev, otp: event.target.value }))}
            />
          </div>
          <button type="button" className="btn-primary mt-5 w-full">
            Submit verification details
          </button>
        </section>

        <section className="card rounded-[28px] bg-stone-900 p-6 text-white">
          <h3 className="text-xl font-bold">Fee rules for verified accounts</h3>
          <div className="mt-5 space-y-3">
            <div className="rounded-[22px] bg-white/10 p-4">
              <p className="font-semibold">Deposit from MoMo or bank</p>
              <p className="mt-2 text-sm text-stone-200">1% fee, capped at GHS 30.</p>
            </div>
            <div className="rounded-[22px] bg-white/10 p-4">
              <p className="font-semibold">Withdrawal to MoMo or bank</p>
              <p className="mt-2 text-sm text-stone-200">1% fee, capped at GHS 30.</p>
            </div>
            <div className="rounded-[22px] bg-white/10 p-4">
              <p className="font-semibold">Use verified balance to pay for purchases</p>
              <p className="mt-2 text-sm text-stone-200">No fee. Spending from Avok verified account should be free.</p>
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
