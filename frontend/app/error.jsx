"use client";

import { useEffect } from "react";

export default function ErrorBoundary({ error, reset }) {
  useEffect(() => {
    console.error("Dashboard error:", error);
  }, [error]);

  return (
    <div className="card rounded-[28px] p-6 text-center">
      <h2 className="text-2xl font-black text-rose-700">Something went wrong</h2>
      <p className="mt-2 text-sm text-stone-600">
        {error?.message || "An unexpected error occurred."}
      </p>
      {reset && (
        <button
          onClick={reset}
          className="btn-primary mt-4"
        >
          Try again
        </button>
      )}
    </div>
  );
}
