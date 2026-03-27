import Link from "next/link";
import { ArrowRight, ShieldCheck, Smartphone, Wallet } from "lucide-react";

const trustPoints = [
  {
    icon: ShieldCheck,
    title: "Funds held securely",
    description: "Every payment stays protected in escrow until delivery is confirmed."
  },
  {
    icon: Smartphone,
    title: "Built for mobile use",
    description: "Clear screens, low-friction steps, and simple actions for busy marketplace users."
  },
  {
    icon: Wallet,
    title: "Clear status at every step",
    description: "Payers, recipients, and admins can always see who holds the money and what happens next."
  }
];

export default function HomePage() {
  return (
    <main className="page-shell">
      <div className="mx-auto flex min-h-[calc(100vh-2rem)] max-w-7xl flex-col justify-center gap-6">
        <section className="hero-grid">
          <div className="card glass rounded-[28px] p-6 sm:p-8 lg:p-10">
            <div className="mb-6 inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-800">
              Trusted escrow for Ghana marketplace payments
            </div>
            <h1 className="max-w-2xl text-4xl font-black leading-tight sm:text-5xl">
              Payers pay with confidence. Recipients deliver with proof. Avok holds the money safely in between.
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-7 text-stone-600 sm:text-lg">
              This frontend is designed to make testing the escrow flow easy. Every screen shows order progress,
              payment safety, dispute actions, and the next expected step.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link href="/login" className="btn-primary inline-flex items-center justify-center gap-2">
                Login to dashboard
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link href="/register" className="btn-secondary inline-flex items-center justify-center gap-2">
                Create an Avok account
              </Link>
            </div>
          </div>

          <div className="card rounded-[28px] border-stone-200 bg-[linear-gradient(180deg,rgba(11,110,79,0.96),rgba(7,63,45,0.96))] p-6 text-white shadow-[0_24px_60px_rgba(7,63,45,0.26)] sm:p-8">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-emerald-100">Trust snapshot</p>
            <div className="mt-6 space-y-4">
              <div className="rounded-3xl bg-white/12 p-5">
                <p className="text-sm text-emerald-100">Escrow balance</p>
                <p className="mt-2 text-4xl font-black">GHS 12,480</p>
                <p className="mt-2 text-sm text-emerald-50">Funds currently protected across active orders</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-3xl bg-white/10 p-4">
                  <p className="text-sm text-emerald-100">Delivery confirmations</p>
                  <p className="mt-1 text-2xl font-bold">94%</p>
                </div>
                <div className="rounded-3xl bg-white/10 p-4">
                  <p className="text-sm text-emerald-100">Disputes resolved</p>
                  <p className="mt-1 text-2xl font-bold">2 days avg</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-3">
          {trustPoints.map((point) => {
            const Icon = point.icon;
            return (
              <article key={point.title} className="card rounded-[24px] p-6">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700">
                  <Icon className="h-5 w-5" />
                </div>
                <h2 className="mt-5 text-xl font-bold">{point.title}</h2>
                <p className="mt-3 text-sm leading-6 text-stone-600">{point.description}</p>
              </article>
            );
          })}
        </section>
      </div>
    </main>
  );
}
