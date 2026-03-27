"use client";

export default function OTPInput({ value, onChange, length = 6, label = "Delivery OTP" }) {
  const padded = Array.from({ length }, (_, index) => value?.[index] || "");

  function handleDigitChange(index, digit) {
    const clean = digit.replace(/\D/g, "").slice(-1);
    const next = [...padded];
    next[index] = clean;
    onChange(next.join(""));
  }

  return (
    <div className="space-y-3">
      <label className="block text-sm font-semibold text-stone-700">{label}</label>
      <div className="flex gap-2">
        {padded.map((digit, index) => (
          <input
            key={index}
            inputMode="numeric"
            maxLength={1}
            value={digit}
            onChange={(event) => handleDigitChange(index, event.target.value)}
            className="h-12 w-12 rounded-2xl border border-stone-200 bg-white text-center text-lg font-bold shadow-sm outline-none focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
          />
        ))}
      </div>
    </div>
  );
}
