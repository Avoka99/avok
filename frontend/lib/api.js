import axios from "axios";

const baseURL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000/api/v1";

export const api = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json"
  }
});

export function setApiToken(token) {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
    return;
  }

  delete api.defaults.headers.common.Authorization;
}

function formatApiErrorDetail(detail) {
  if (detail == null) return null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item == null) return "";
        if (typeof item === "string") return item;
        if (typeof item === "object" && item.msg != null) {
          const loc = Array.isArray(item.loc) ? item.loc.filter(Boolean).join(".") : "";
          return loc ? `${loc}: ${item.msg}` : String(item.msg);
        }
        try {
          return JSON.stringify(item);
        } catch {
          return String(item);
        }
      })
      .filter(Boolean)
      .join("; ");
  }
  if (typeof detail === "object" && detail.message != null) return String(detail.message);
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error?.response?.status;
    const data = error?.response?.data;
    const formatted = formatApiErrorDetail(data?.detail);
    let message =
      formatted ||
      data?.message ||
      error?.message ||
      "Something went wrong while contacting the API.";

    if (status === 401 && typeof window !== "undefined") {
      try {
        const { useAuthStore } = await import("@/stores/auth-store");
        useAuthStore.getState().logout();
      } catch {
        setApiToken(null);
        window.localStorage.removeItem("avok-auth");
      }
      if (!window.location.pathname.startsWith("/login")) {
        message =
          typeof message === "string" && message.trim() && message !== "Network Error"
            ? message
            : "Session expired or not signed in. Please log in again.";
        window.setTimeout(() => {
          window.location.assign("/login?reason=session");
        }, 1400);
      }
    }

    return Promise.reject(new Error(message));
  }
);
