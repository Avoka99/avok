"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { api, setApiToken } from "@/lib/api";

function decodeTokenPayload(token) {
  try {
    const payload = token.split(".")[1];
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(normalized));
  } catch {
    return null;
  }
}

function normalizeUserRole(user) {
  if (!user) {
    return "buyer";
  }

  if (user.role) {
    return user.role;
  }

  if (user.is_superuser) {
    return "admin";
  }

  return "buyer";
}

export const useAuthStore = create(
  persist(
    (set, get) => ({
      accessToken: null,
      user: null,
      hydrated: false,
      setHydrated: (value) => set({ hydrated: value }),
      bootstrap: () => {
        const token = get().accessToken;
        setApiToken(token);
      },
      login: async (payload) => {
        const response = await api.post("/auth/login", payload);
        const accessToken = response.data?.access_token || response.data?.token || null;
        const decoded = accessToken ? decodeTokenPayload(accessToken) : null;
        const fallbackUser = accessToken
          ? {
              id: decoded?.sub ? Number(decoded.sub) : null,
              phone_number: payload.phone_number,
              role: decoded?.role || "buyer",
              is_superuser: decoded?.role === "super_admin" || decoded?.role === "admin"
            }
          : null;
        const user = response.data?.user
          ? { ...response.data.user, role: normalizeUserRole(response.data.user) }
          : fallbackUser;

        setApiToken(accessToken);
        set({ accessToken, user });
        return response.data;
      },
      register: async (payload) => {
        const response = await api.post("/auth/register", payload);
        return response.data;
      },
      setSession: ({ accessToken, user }) => {
        setApiToken(accessToken);
        set({ accessToken, user: user ? { ...user, role: normalizeUserRole(user) } : null });
      },
      logout: () => {
        setApiToken(null);
        set({ accessToken: null, user: null });
      },
      setUser: (user) => set({ user: user ? { ...user, role: normalizeUserRole(user) } : null })
    }),
    {
      name: "avok-auth",
      onRehydrateStorage: () => (state) => {
        state?.setHydrated?.(true);
        state?.bootstrap?.();
      }
    }
  )
);
