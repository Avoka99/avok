"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

function formatDate(value) {
  if (!value) {
    return "Just now";
  }

  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

function formatChannel(value) {
  return String(value || "in_app").replaceAll("_", " ");
}

export default function NotificationsPage() {
  const notificationsQuery = useQuery({
    queryKey: ["notifications"],
    queryFn: async () => {
      const response = await api.get("/notifications");
      return response.data;
    }
  });

  const notifications = notificationsQuery.data || [];

  return (
    <div className="space-y-5">
      <section className="card rounded-[28px] p-6">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Notifications</p>
        <h2 className="mt-3 text-3xl font-black">Important escrow changes stay visible so users are never left guessing.</h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-stone-600">
          Avok stores each important session update here and includes a direct monitoring link back to the checkout session whenever one is available.
        </p>
      </section>

      {notificationsQuery.isLoading ? (
        <section className="card rounded-[24px] p-5">
          <p className="text-sm text-stone-600">Loading notifications...</p>
        </section>
      ) : null}

      {notificationsQuery.isError ? (
        <section className="card rounded-[24px] p-5">
          <p className="text-sm text-rose-700">{notificationsQuery.error.message}</p>
        </section>
      ) : null}

      {!notificationsQuery.isLoading && !notificationsQuery.isError && notifications.length === 0 ? (
        <section className="card rounded-[24px] p-5">
          <h3 className="text-lg font-bold">No notifications yet</h3>
          <p className="mt-2 text-sm leading-6 text-stone-600">
            When a checkout session is created, funded, disputed, refunded, or released, the important updates will appear here with a direct link back to the escrow session.
          </p>
        </section>
      ) : null}

      <section className="space-y-4">
        {notifications.map((notification) => (
          <article key={notification.id} className="card rounded-[24px] p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-stone-500">
                  <span>{formatChannel(notification.notification_type)}</span>
                  <span className="rounded-full bg-stone-100 px-2 py-1 text-[11px] tracking-[0.12em] text-stone-700">
                    {notification.status}
                  </span>
                </div>
                <h3 className="mt-3 text-lg font-bold">{notification.title}</h3>
                <p className="mt-2 text-sm leading-6 text-stone-600">{notification.content}</p>
              </div>
              <p className="text-sm text-stone-500">{formatDate(notification.sent_at || notification.created_at)}</p>
            </div>

            <div className="mt-4 flex flex-wrap gap-3 text-sm text-stone-600">
              {notification.order_reference ? <span>Session: {notification.order_reference}</span> : null}
              <span>Delivered to: {notification.recipient}</span>
            </div>

            {notification.action_url ? (
              <div className="mt-4">
                <Link href={notification.action_url.replace(/^https?:\/\/[^/]+/, "")} className="btn-secondary inline-flex">
                  Monitor escrow session
                </Link>
              </div>
            ) : null}
          </article>
        ))}
      </section>
    </div>
  );
}
