"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { BookOpen, Star, Library, User, Upload, Menu, X, LogIn, LogOut } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

const NAV_ITEMS = [
  { href: "/", label: "홈", icon: BookOpen },
  { href: "/recommendations", label: "책 추천", icon: Star },
  { href: "/library", label: "내 서재", icon: Library },
  { href: "/mypage", label: "마이페이지", icon: User },
];

/** 로고 컴포넌트 */
function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2 cursor-pointer group">
      <div
        className="w-8 h-8 rounded-xl flex items-center justify-center"
        style={{ background: "var(--accent)" }}
      >
        <BookOpen size={16} color="white" strokeWidth={2.5} />
      </div>
      <span
        className="font-bold text-lg tracking-tight"
        style={{ color: "var(--text-primary)" }}
      >
        북치기박치기
      </span>
    </Link>
  );
}

/** 유저 아바타 — 프로필 이미지 or 이니셜 */
function UserAvatar({ user }: { user: { name: string; profile_image?: string | null } }) {
  const initial = user.name.charAt(0).toUpperCase();

  const fallback = (
    <div
      className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
      style={{ background: "var(--accent)" }}
    >
      {initial}
    </div>
  );

  if (!user.profile_image) return fallback;

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={user.profile_image}
      alt={user.name}
      referrerPolicy="no-referrer"
      className="w-8 h-8 rounded-full object-cover flex-shrink-0"
      onError={(e) => {
        const target = e.currentTarget;
        target.style.display = "none";
        const parent = target.parentElement;
        if (parent) {
          const div = document.createElement("div");
          div.className = "w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-bold flex-shrink-0";
          div.style.background = "var(--accent)";
          div.textContent = initial;
          parent.insertBefore(div, target);
        }
      }}
    />
  );
}

/** 데스크탑 헤더 네비게이션 */
export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { user, logout } = useAuth();

  return (
    <>
      <header
        className="sticky top-0 z-40 w-full"
        style={{
          background: "rgba(255, 253, 249, 0.92)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid var(--border-default)",
        }}
      >
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <Logo />

          {/* 데스크탑 메뉴 */}
          <nav className="hidden md:flex items-center gap-1">
            {NAV_ITEMS.map(({ href, label }) => {
              const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className="px-4 py-2 rounded-xl text-sm font-medium transition-all duration-150 cursor-pointer"
                  style={{
                    color: isActive ? "var(--accent-dark)" : "var(--text-secondary)",
                    background: isActive ? "var(--accent-light)" : "transparent",
                    fontWeight: isActive ? 600 : 500,
                  }}
                >
                  {label}
                </Link>
              );
            })}
          </nav>

          {/* 데스크탑 우측 */}
          <div className="hidden md:flex items-center gap-2">
            {user ? (
              <>
                <Link href="/library/search" className="btn-secondary text-sm">
                  <BookOpen size={15} />
                  책 추가
                </Link>
                <div className="flex items-center gap-2 pl-2" style={{ borderLeft: "1px solid var(--border-default)" }}>
                  <UserAvatar user={user} />
                  <span className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
                    {user.name}
                  </span>
                  <button
                    onClick={logout}
                    className="p-1.5 rounded-lg transition-colors cursor-pointer"
                    style={{ color: "var(--text-muted)" }}
                    title="로그아웃"
                  >
                    <LogOut size={16} />
                  </button>
                </div>
              </>
            ) : (
              <button
                onClick={() => router.push("/login")}
                className="btn-primary text-sm"
              >
                <LogIn size={15} />
                로그인
              </button>
            )}
          </div>

          {/* 모바일 햄버거 */}
          <button
            className="md:hidden p-2 rounded-xl transition-colors cursor-pointer"
            style={{ color: "var(--text-secondary)" }}
            onClick={() => setDrawerOpen(true)}
            aria-label="메뉴 열기"
          >
            <Menu size={22} />
          </button>
        </div>
      </header>

      {/* 모바일 드로어 오버레이 */}
      {drawerOpen && (
        <div
          className="fixed inset-0 z-50 md:hidden"
          onClick={() => setDrawerOpen(false)}
          style={{ background: "rgba(28, 25, 23, 0.4)", backdropFilter: "blur(2px)" }}
        />
      )}

      {/* 모바일 사이드 드로어 */}
      <aside
        className="fixed top-0 left-0 bottom-0 z-50 w-72 md:hidden flex flex-col transition-transform duration-300 ease-out"
        style={{
          background: "var(--bg-card)",
          boxShadow: "var(--shadow-lg)",
          transform: drawerOpen ? "translateX(0)" : "translateX(-100%)",
        }}
      >
        {/* 드로어 헤더 */}
        <div
          className="flex items-center justify-between px-5 h-14"
          style={{ borderBottom: "1px solid var(--border-default)" }}
        >
          <Logo />
          <button
            className="p-2 rounded-xl transition-colors cursor-pointer"
            style={{ color: "var(--text-muted)" }}
            onClick={() => setDrawerOpen(false)}
            aria-label="메뉴 닫기"
          >
            <X size={20} />
          </button>
        </div>

        {/* 드로어 유저 정보 */}
        {user && (
          <div
            className="flex items-center gap-3 px-5 py-4"
            style={{ borderBottom: "1px solid var(--border-default)" }}
          >
            <UserAvatar user={user} />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate" style={{ color: "var(--text-primary)" }}>
                {user.name}
              </p>
              <p className="text-xs truncate" style={{ color: "var(--text-muted)" }}>
                {user.email}
              </p>
            </div>
          </div>
        )}

        {/* 드로어 메뉴 */}
        <nav className="flex flex-col gap-1 p-4 flex-1">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                onClick={() => setDrawerOpen(false)}
                className="flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-150 cursor-pointer"
                style={{
                  color: isActive ? "var(--accent-dark)" : "var(--text-primary)",
                  background: isActive ? "var(--accent-light)" : "transparent",
                  fontWeight: isActive ? 600 : 400,
                }}
              >
                <Icon size={18} strokeWidth={isActive ? 2.5 : 2} />
                <span className="text-[15px]">{label}</span>
              </Link>
            );
          })}

          <div className="mt-4" style={{ borderTop: "1px solid var(--border-default)", paddingTop: "16px" }}>
            {user ? (
              <>
                <Link
                  href="/library/search"
                  onClick={() => setDrawerOpen(false)}
                  className="flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-150 cursor-pointer"
                  style={{ color: "var(--text-secondary)", fontWeight: 500 }}
                >
                  <BookOpen size={18} strokeWidth={2} />
                  <span className="text-[15px]">책 추가하기</span>
                </Link>
                <Link
                  href="/mypage"
                  onClick={() => setDrawerOpen(false)}
                  className="flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-150 cursor-pointer"
                  style={{ color: "var(--text-secondary)", fontWeight: 500 }}
                >
                  <Upload size={18} strokeWidth={2} />
                  <span className="text-[15px]">CSV 임포트</span>
                </Link>
                <button
                  onClick={() => { logout(); setDrawerOpen(false); }}
                  className="w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-150 cursor-pointer"
                  style={{ color: "var(--text-muted)", fontWeight: 500 }}
                >
                  <LogOut size={18} strokeWidth={2} />
                  <span className="text-[15px]">로그아웃</span>
                </button>
              </>
            ) : (
              <button
                onClick={() => { router.push("/login"); setDrawerOpen(false); }}
                className="w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-150 cursor-pointer"
                style={{ color: "var(--accent-dark)", fontWeight: 600 }}
              >
                <LogIn size={18} strokeWidth={2} />
                <span className="text-[15px]">로그인</span>
              </button>
            )}
          </div>
        </nav>
      </aside>
    </>
  );
}
