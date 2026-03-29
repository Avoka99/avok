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
    return "user";
  }

  if (user.role) {
    return user.role === "buyer" || user.role === "seller" ? "user" : user.role;
  }

  if (user.is_superuser) {
    return "super_admin";
  }

  return "user";
}

export const useAuthStore = create(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
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
        const refreshToken = response.data?.refresh_token || null;
        
        setApiToken(accessToken);
        
        // Fetch user profile after login to get avok_account_number
        try {
          const userResponse = await api.get("/auth/me");
          const user = { 
            ...userResponse.data, 
            role: normalizeUserRole(userResponse.data) 
          };
          set({ accessToken, refreshToken, user });
        } catch (e) {
          // Fallback if /me fails
          const decoded = accessToken ? decodeTokenPayload(accessToken) : null;
          const fallbackUser = {
            id: decoded?.sub ? Number(decoded.sub) : null,
            phone_number: payload.phone_number,
            role: decoded?.role || "user",
            is_superuser: decoded?.role === "super_admin" || decoded?.role === "admin"
          };
          set({ accessToken, refreshToken, user: fallbackUser });
        }
        
        return response.data;
      },
      register: async (payload) => {
        const response = await api.post("/auth/register", payload);
        return response.data;
      },
      setSession: ({ accessToken, refreshToken = null, user }) => {
        setApiToken(accessToken);
        set({
          accessToken,
          refreshToken,
          user: user ? { ...user, role: normalizeUserRole(user) } : null
        });
      },
      logout: () => {
        setApiToken(null);
        set({ accessToken: null, refreshToken: null, user: null });
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
