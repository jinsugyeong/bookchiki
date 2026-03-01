"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

/** 로그인 필수 페이지에서 사용 — 비로그인 시 /login으로 리다이렉트 */
export function useRequireAuth() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/login");
    }
  }, [user, isLoading, router]);

  return { user, isLoading };
}
