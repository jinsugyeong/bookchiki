"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { BookOpen, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

function buildGoogleOAuthUrl() {
  const redirectUri = `${window.location.origin}/auth/callback`;
  const params = new URLSearchParams({
    client_id: GOOGLE_CLIENT_ID ?? "",
    redirect_uri: redirectUri,
    response_type: "code",
    scope: "openid email profile",
    access_type: "offline",
    prompt: "select_account",
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${params}`;
}

export default function LoginPage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  /** 이미 로그인된 경우 홈으로 */
  useEffect(() => {
    if (!isLoading && user) router.replace("/");
  }, [user, isLoading, router]);

  const handleGoogleLogin = () => {
    window.location.href = buildGoogleOAuthUrl();
  };

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ background: "var(--bg-base)" }}
    >
      {/* 상단 네비 — 풀 width 헤더처럼 */}
      <div
        className="px-5 py-3 flex items-center justify-between"
        style={{ borderBottom: "1px solid var(--border-default)" }}
      >
        {/* 브랜드 로고 */}
        <Link href="/" className="flex items-center gap-2 cursor-pointer">
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: "var(--accent)" }}
          >
            <BookOpen size={16} color="white" strokeWidth={2.5} />
          </div>
          <span
            className="text-sm font-bold tracking-tight"
            style={{ color: "var(--text-primary)" }}
          >
            북치기박치기
          </span>
        </Link>

        {/* 홈으로 버튼 */}
        <Link
          href="/"
          className="flex items-center gap-1.5 text-sm font-medium px-3.5 py-2 rounded-xl transition-colors cursor-pointer"
          style={{
            color: "var(--text-secondary)",
            background: "var(--bg-subtle)",
            border: "1px solid var(--border-default)",
          }}
        >
          <ArrowLeft size={14} />
          홈으로
        </Link>
      </div>

      {/* 로그인 카드 */}
      <div className="flex-1 flex items-center justify-center px-4">
        <div
          className="w-full max-w-sm rounded-3xl p-8 flex flex-col items-center gap-6"
          style={{
            background: "var(--bg-card)",
            boxShadow: "var(--shadow-md)",
            border: "1px solid var(--border-default)",
          }}
        >
          {/* 로고 */}
          <div className="flex flex-col items-center gap-3">
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center"
              style={{ background: "var(--accent)" }}
            >
              <BookOpen size={28} color="white" strokeWidth={2.5} />
            </div>
            <div className="text-center">
              <h1
                className="text-xl font-bold tracking-tight"
                style={{ color: "var(--text-primary)" }}
              >
                북치기박치기
              </h1>
              <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
                독서 기록 &amp; AI 책 추천
              </p>
            </div>
          </div>

          {/* 구분선 */}
          <div className="w-full" style={{ borderTop: "1px solid var(--border-default)" }} />

          <div className="w-full flex flex-col gap-3">
            <p
              className="text-center text-sm font-medium"
              style={{ color: "var(--text-secondary)" }}
            >
              계속하려면 로그인하세요
            </p>

            {/* Google 로그인 버튼 */}
            <button
              onClick={handleGoogleLogin}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 rounded-xl font-medium text-sm transition-all duration-150 cursor-pointer"
              style={{
                background: "white",
                border: "1px solid #e0e0e0",
                color: "#3c4043",
                boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.12)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.boxShadow = "0 1px 3px rgba(0,0,0,0.08)";
              }}
            >
              {/* Google SVG 로고 */}
              <svg width="18" height="18" viewBox="0 0 18 18">
                <path
                  fill="#4285F4"
                  d="M16.51 8H8.98v3h4.3c-.18 1-.74 1.48-1.6 2.04v2.01h2.6a7.8 7.8 0 0 0 2.38-5.88c0-.57-.05-.66-.15-1.18z"
                />
                <path
                  fill="#34A853"
                  d="M8.98 17c2.16 0 3.97-.72 5.3-1.94l-2.6-2a4.8 4.8 0 0 1-7.18-2.54H1.83v2.07A8 8 0 0 0 8.98 17z"
                />
                <path
                  fill="#FBBC05"
                  d="M4.5 10.52a4.8 4.8 0 0 1 0-3.04V5.41H1.83a8 8 0 0 0 0 7.18l2.67-2.07z"
                />
                <path
                  fill="#EA4335"
                  d="M8.98 4.18c1.17 0 2.23.4 3.06 1.2l2.3-2.3A8 8 0 0 0 1.83 5.4L4.5 7.49a4.77 4.77 0 0 1 4.48-3.3z"
                />
              </svg>
              Google로 로그인
            </button>
          </div>

          <p
            className="text-center text-xs leading-relaxed"
            style={{ color: "var(--text-muted)" }}
          >
            로그인하면 서비스 이용약관 및 개인정보 처리방침에 동의하는 것으로 간주됩니다.
          </p>
        </div>
      </div>
    </div>
  );
}
