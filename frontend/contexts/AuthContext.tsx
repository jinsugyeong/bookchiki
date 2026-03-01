"use client";

import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";

interface AuthUser {
  id: string;
  email: string;
  name: string;
  profile_image?: string | null;
}

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  login: (token: string, user: AuthUser) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  /** 앱 시작 시 저장된 토큰으로 유저 정보 복원 */
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setIsLoading(false);
      return;
    }
    api
      .get("/auth/me")
      .then(({ data }) => setUser(data))
      .catch(() => localStorage.removeItem("access_token"))
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback((token: string, userData: AuthUser) => {
    localStorage.setItem("access_token", token);
    setUser(userData);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("access_token");
    setUser(null);
    router.push("/");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
