"use client";

import { useRef, useEffect } from "react";

export default function OTPInput({ value, onChange, length = 6, label = "Delivery OTP" }) {
  const padded = Array.from({ length }, (_, index) => value?.[index] || "");
  const inputRefs = useRef([]);

  useEffect(() => {
    if (inputRefs.current[0]) {
      inputRefs.current[0].focus();
    }
  }, []);

  function handleDigitChange(index, digit) {
    const clean = digit.replace(/\D/g, "").slice(-1);
    const next = [...padded];
    next[index] = clean;
    onChange(next.join(""));

    // Auto-advance to next input
    if (clean && index < length - 1 && inputRefs.current[index + 1]) {
      inputRefs.current[index + 1].focus();
    }
  }

  function handleKeyDown(index, event) {
    if (event.key === "Backspace" && !padded[index] && index > 0) {
      // Move to previous input on backspace when current is empty
      inputRefs.current[index - 1]?.focus();
      const next = [...padded];
      next[index - 1] = "";
      onChange(next.join(""));
    }
  }

  function handlePaste(event) {
    event.preventDefault();
    const pasted = event.clipboardData.getData("text").replace(/\D/g, "").slice(0, length);
    if (!pasted) return;

    const next = [...padded];
    for (let i = 0; i < pasted.length; i++) {
      next[i] = pasted[i];
    }
    onChange(next.join(""));

    // Focus the input after the last pasted digit
    const focusIndex = Math.min(pasted.length, length - 1);
    inputRefs.current[focusIndex]?.focus();
  }

  return (
    <div className="space-y-3">
      <label className="block text-sm font-semibold text-stone-700">{label}</label>
      <div className="flex gap-2" onPaste={handlePaste}>
        {padded.map((digit, index) => (
          <input
            key={index}
            ref={(el) => (inputRefs.current[index] = el)}
            inputMode="numeric"
            maxLength={1}
            value={digit}
            onChange={(event) => handleDigitChange(index, event.target.value)}
            onKeyDown={(event) => handleKeyDown(index, event)}
            className="h-12 w-12 rounded-2xl border border-stone-200 bg-white text-center text-lg font-bold shadow-sm outline-none focus:border-emerald-500 focus:ring-4 focus:ring-emerald-100"
          />
        ))}
      </div>
    </div>
  );
}
