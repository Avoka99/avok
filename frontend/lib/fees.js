export function calculateCappedFee(amount, percent = 0.01, cap = 30) {
  const numeric = Number(amount || 0);
  if (!numeric || numeric <= 0) {
    return 0;
  }

  return Math.min(numeric * percent, cap);
}

export function formatGhs(amount) {
  return new Intl.NumberFormat("en-GH", {
    style: "currency",
    currency: "GHS",
    maximumFractionDigits: 2
  }).format(Number(amount || 0));
}
