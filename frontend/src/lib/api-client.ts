import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:18000/api/v1";
const AUTH_COOKIE_MODE = process.env.NEXT_PUBLIC_AUTH_COOKIE_MODE === "true";
const CSRF_COOKIE_NAME = process.env.NEXT_PUBLIC_AUTH_CSRF_COOKIE_NAME || "csrf_token";
const CSRF_HEADER_NAME = process.env.NEXT_PUBLIC_AUTH_CSRF_HEADER_NAME || "X-CSRF-Token";

type RetryableRequestConfig = InternalAxiosRequestConfig & { _retry?: boolean };

interface RefreshTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: AUTH_COOKIE_MODE,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

let refreshPromise: Promise<string | null> | null = null;

function clearAuthStorage() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("user");
}

function getCookieValue(name: string): string | null {
  if (typeof document === "undefined") return null;
  const cookies = document.cookie ? document.cookie.split("; ") : [];
  for (const item of cookies) {
    const [k, ...rest] = item.split("=");
    if (k === name) {
      return decodeURIComponent(rest.join("="));
    }
  }
  return null;
}

function redirectToLogin() {
  if (typeof window === "undefined") return;
  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

function isAuthEndpoint(url?: string): boolean {
  if (!url) return false;
  return (
    url.includes("/auth/login") ||
    url.includes("/auth/register") ||
    url.includes("/auth/refresh")
  );
}

async function refreshAccessToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;

  try {
    const refreshToken = localStorage.getItem("refresh_token");
    const payload = AUTH_COOKIE_MODE ? {} : { refresh_token: refreshToken };
    if (!AUTH_COOKIE_MODE && !refreshToken) return null;

    const response = await axios.post<RefreshTokenResponse>(
      `${API_BASE_URL}/auth/refresh`,
      payload,
      {
        headers: {
          "Content-Type": "application/json",
          ...(AUTH_COOKIE_MODE && getCookieValue(CSRF_COOKIE_NAME)
            ? { [CSRF_HEADER_NAME]: getCookieValue(CSRF_COOKIE_NAME) as string }
            : {}),
        },
        withCredentials: AUTH_COOKIE_MODE,
        timeout: 10000,
      }
    );
    localStorage.setItem("access_token", response.data.access_token);
    if (!AUTH_COOKIE_MODE) {
      localStorage.setItem("refresh_token", response.data.refresh_token);
    }
    return response.data.access_token;
  } catch {
    clearAuthStorage();
    return null;
  }
}

// Request interceptor: attach JWT Bearer token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      if (AUTH_COOKIE_MODE && config.headers && config.method?.toUpperCase() !== "GET") {
        const csrfToken = getCookieValue(CSRF_COOKIE_NAME);
        if (csrfToken) {
          config.headers[CSRF_HEADER_NAME] = csrfToken;
        }
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor: handle 401 by redirecting to /login
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const status = error.response?.status;
    const originalRequest = error.config as RetryableRequestConfig | undefined;

    if (
      status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isAuthEndpoint(originalRequest.url)
    ) {
      originalRequest._retry = true;

      if (!refreshPromise) {
        refreshPromise = refreshAccessToken().finally(() => {
          refreshPromise = null;
        });
      }

      const newAccessToken = await refreshPromise;
      if (newAccessToken) {
        originalRequest.headers = originalRequest.headers ?? {};
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest);
      }

      clearAuthStorage();
      redirectToLogin();
      return Promise.reject(error);
    }

    if (status === 401) {
      clearAuthStorage();
      redirectToLogin();
    }

    return Promise.reject(error);
  }
);

export default apiClient;
