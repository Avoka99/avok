"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { api, setApiToken } from "@/lib/api";

let refreshTimeoutId = null;
let refreshRequest = null;

function setAuthCookie(token) {
  if (typeof document === "undefined") return;
  if (token) {
    document.cookie = `avok-auth=${token}; path=/; max-age=86400; SameSite=Lax`;
  } else {
    document.cookie = "avok-auth=; path=/; max-age=0";
  }
}

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
    const role = user.role.toLowerCase();
    if (role === "buyer" || role === "seller") {
      return "user";
    }
    return role;
  }

  if (user.is_superuser) {
    return "super_admin";
  }

  return "user";
}

function clearScheduledRefresh() {
  if (typeof window === "undefined") return;
  if (refreshTimeoutId) {
    window.clearTimeout(refreshTimeoutId);
    refreshTimeoutId = null;
  }
}

function scheduleRefresh(get) {
  if (typeof window === "undefined") return;
  clearScheduledRefresh();

  const { accessToken, refreshToken, user } = get();
  if (!accessToken || !refreshToken || user?.is_guest) {
    return;
  }

  const payload = decodeTokenPayload(accessToken);
  const expiresAt = Number(payload?.exp || 0) * 1000;
  if (!expiresAt) {
    return;
  }

  const delay = Math.max(expiresAt - Date.now() - 60_000, 5_000);
  refreshTimeoutId = window.setTimeout(() => {
    get().refreshSession().catch(() => {
      get().logout({ localOnly: true });
    });
  }, delay);
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
        setAuthCookie(token);
        scheduleRefresh(get);
      },
      clearSession: () => {
        clearScheduledRefresh();
        setApiToken(null);
        setAuthCookie(null);
        try {
          localStorage.removeItem("avok-guest-session");
        } catch {}
        set({ accessToken: null, refreshToken: null, user: null });
      },
      login: async (payload) => {
        const response = await api.post("/auth/login", payload);
        const accessToken = response.data?.access_token || response.data?.token || null;
        const refreshToken = response.data?.refresh_token || null;
        
        setApiToken(accessToken);
        setAuthCookie(accessToken);
        
        // Fetch user profile after login to get avok_account_number
        try {
          const userResponse = await api.get("/auth/me");
          const user = { 
            ...userResponse.data, 
            role: normalizeUserRole(userResponse.data) 
          };
          set({ accessToken, refreshToken, user });
          scheduleRefresh(get);
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
          scheduleRefresh(get);
        }
        
        return response.data;
      },
      register: async (payload) => {
        const response = await api.post("/auth/register", payload);
        return response.data;
      },
      setSession: ({ accessToken, refreshToken = null, user, isGuest = false }) => {
        if (isGuest) {
          // Guest sessions are stored separately and do NOT grant dashboard access
          try {
            localStorage.setItem("avok-guest-session", JSON.stringify({ accessToken, refreshToken, user }));
          } catch (e) {
            // localStorage may be unavailable
          }
          set({
            accessToken,
            refreshToken,
            user: user ? { ...user, role: "guest", is_guest: true } : null
          });
        } else {
          setApiToken(accessToken);
          setAuthCookie(accessToken);
          set({
            accessToken,
            refreshToken,
            user: user ? { ...user, role: normalizeUserRole(user) } : null
          });
          scheduleRefresh(get);
        }
      },
      refreshSession: async () => {
        const { refreshToken, user } = get();
        if (!refreshToken || user?.is_guest) {
          throw new Error("No refresh session available.");
        }

        if (!refreshRequest) {
          refreshRequest = api
            .post(
              "/auth/refresh",
              { refresh_token: refreshToken },
              { skipAuthRefresh: true }
            )
            .then((response) => {
              const nextAccessToken = response.data?.access_token || null;
              const nextRefreshToken = response.data?.refresh_token || null;
              setApiToken(nextAccessToken);
              setAuthCookie(nextAccessToken);
              set((state) => ({
                accessToken: nextAccessToken,
                refreshToken: nextRefreshToken,
                user: state.user,
              }));
              scheduleRefresh(get);
              return response.data;
            })
            .finally(() => {
              refreshRequest = null;
            });
        }

        return refreshRequest;
      },
      logout: async ({ localOnly = false } = {}) => {
        const { accessToken, refreshToken } = get();
        clearScheduledRefresh();

        if (!localOnly && (accessToken || refreshToken)) {
          try {
            await api.post(
              "/auth/logout",
              { refresh_token: refreshToken },
              {
                headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
                skipAuthRefresh: true,
              }
            );
          } catch {}
        }

        get().clearSession();
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
