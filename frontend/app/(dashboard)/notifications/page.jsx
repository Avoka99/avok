const alerts = [
  { title: "Payment successful", body: "Your funds are now held securely in escrow for order AVK-ORDER-1001." },
  { title: "Shipment update", body: "The recipient marked your session as shipped and generated a delivery OTP." },
  { title: "Reminder", body: "Confirm delivery when the product arrives so escrow can release the funds." },
  { title: "Dispute update", body: "Admin review is in progress. Both administrators must agree before final action." }
];

export default function NotificationsPage() {
  return (
    <div className="space-y-5">
      <section className="card rounded-[28px] p-6">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Notifications</p>
        <h2 className="mt-3 text-3xl font-black">Important status changes stay visible so users are never left guessing.</h2>
      </section>

      <section className="space-y-4">
        {alerts.map((alert) => (
          <article key={alert.title} className="card rounded-[24px] p-5">
            <h3 className="text-lg font-bold">{alert.title}</h3>
            <p className="mt-2 text-sm leading-6 text-stone-600">{alert.body}</p>
          </article>
        ))}
      </section>
    </div>
  );
}
