"use client";

import {
  createContext,
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import apiClient from "@/lib/api-client";
import type { User, LoginRequest, RegisterRequest, AuthTokenResponse } from "@/types/user";

const AUTH_COOKIE_MODE = process.env.NEXT_PUBLIC_AUTH_COOKIE_MODE === "true";

export interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

async function fetchCurrentUser(): Promise<User> {
  const response = await apiClient.get<User>("/auth/me");
  return response.data;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  // Load user on mount: verify token by calling /auth/me
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      fetchCurrentUser()
        .then((userData) => {
          setUser(userData);
          localStorage.setItem("user", JSON.stringify(userData));
        })
        .catch(() => {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          localStorage.removeItem("user");
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(
    async (data: LoginRequest) => {
      const response = await apiClient.post<AuthTokenResponse>("/auth/login", data);
      const { access_token, refresh_token } = response.data;
      localStorage.setItem("access_token", access_token);
      if (!AUTH_COOKIE_MODE) {
        localStorage.setItem("refresh_token", refresh_token);
      } else {
        localStorage.removeItem("refresh_token");
      }

      // Fetch user profile
      const userData = await fetchCurrentUser();
      localStorage.setItem("user", JSON.stringify(userData));
      setUser(userData);
      router.push("/dashboard");
    },
    [router]
  );

  const register = useCallback(
    async (data: RegisterRequest) => {
      const response = await apiClient.post<AuthTokenResponse>("/auth/register", data);
      const { access_token, refresh_token } = response.data;
      localStorage.setItem("access_token", access_token);
      if (!AUTH_COOKIE_MODE) {
        localStorage.setItem("refresh_token", refresh_token);
      } else {
        localStorage.removeItem("refresh_token");
      }

      // Fetch user profile
      const userData = await fetchCurrentUser();
      localStorage.setItem("user", JSON.stringify(userData));
      setUser(userData);
      router.push("/dashboard");
    },
    [router]
  );

  const logout = useCallback(() => {
    const refreshToken = localStorage.getItem("refresh_token");
    if (AUTH_COOKIE_MODE) {
      void apiClient.post("/auth/logout", {});
    } else if (refreshToken) {
      void apiClient.post("/auth/logout", { refresh_token: refreshToken });
    }
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("user");
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
