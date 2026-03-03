"use client";

import { useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { loginWithGoogle } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import LoadingSpinner from "@/components/ui/LoadingSpinner";

function CallbackHandler() {
  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const called = useRef(false);

  useEffect(() => {
    if (called.current) return;
    called.current = true;

    const code = searchParams.get("code");
    const error = searchParams.get("error");

    if (error || !code) {
      router.replace("/login");
      return;
    }

    loginWithGoogle(code)
      .then((data) => {
        login(data.access_token, data.refresh_token, data.user);
        router.replace("/");
      })
      .catch(() => {
        router.replace("/login");
      });
  }, [searchParams, login, router]);

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center gap-4"
      style={{ background: "var(--bg-base)" }}
    >
      <LoadingSpinner />
      <p className="text-sm" style={{ color: "var(--text-muted)" }}>
        로그인 처리 중...
      </p>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--bg-base)" }}>
        <LoadingSpinner />
      </div>
    }>
      <CallbackHandler />
    </Suspense>
  );
}
