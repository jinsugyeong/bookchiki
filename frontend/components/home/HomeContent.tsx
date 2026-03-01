"use client";

import Link from "next/link";
import Image from "next/image";
import {
  BookOpen,
  Star,
  Library,
  ArrowRight,
  Sparkles,
  LogIn,
  BookMarked,
  MessageCircle,
  TrendingUp,
  Upload,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import StatsDashboard from "@/components/home/StatsDashboard";

/* ─────────────────────────────────────────────────────────
   로그인 사용자 홈
───────────────────────────────────────────────────────── */
function LoggedInHome({ name }: { name: string }) {
  return (
    <div className="flex flex-col gap-8">
      {/* 히어로 */}
      <section className="animate-fade-in">
        <div
          className="relative rounded-3xl overflow-hidden px-6 py-10 md:px-10 md:py-14"
          style={{
            background: "linear-gradient(135deg, #FEF9F4 0%, #FEF3C7 50%, #FEF9F4 100%)",
            border: "1px solid var(--border-default)",
          }}
        >
          <div
            className="absolute top-0 right-0 w-48 h-48 rounded-full"
            style={{
              background: "radial-gradient(circle, rgba(232,160,69,0.12) 0%, transparent 70%)",
              transform: "translate(25%, -25%)",
            }}
          />
          <div
            className="absolute bottom-0 left-0 w-32 h-32 rounded-full"
            style={{
              background: "radial-gradient(circle, rgba(232,160,69,0.08) 0%, transparent 70%)",
              transform: "translate(-25%, 25%)",
            }}
          />

          <div className="relative flex flex-col md:flex-row md:items-center md:justify-between gap-6">
            <div className="flex flex-col gap-3 max-w-md">
              <div
                className="badge w-fit"
                style={{ background: "var(--accent-light)", color: "var(--accent-dark)" }}
              >
                <Sparkles size={11} />
                AI 기반 독서 추천
              </div>
              <h1
                className="text-3xl md:text-4xl font-extrabold tracking-tight leading-tight"
                style={{ color: "var(--text-primary)" }}
              >
                안녕하세요, {name.split(" ")[0]}님! 👋<br />
                오늘도 좋은 책 찾아드려요
              </h1>
              <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                독서 기록과 별점으로 AI가 당신의 취향을 분석해서<br />
                완벽한 다음 책을 추천해드려요.
              </p>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row md:flex-col">
              <Link href="/recommendations" className="btn-primary text-sm justify-center">
                <Star size={15} />
                AI 추천 받기
                <ArrowRight size={14} />
              </Link>
              <Link href="/library/search" className="btn-secondary text-sm justify-center">
                <BookOpen size={15} />
                책 추가하기
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* 독서 통계 */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-bold" style={{ color: "var(--text-primary)" }}>
            내 독서 현황
          </h2>
          <Link
            href="/library"
            className="text-xs font-medium flex items-center gap-1 transition-colors cursor-pointer"
            style={{ color: "var(--accent-dark)" }}
          >
            서재 보기
            <ArrowRight size={13} />
          </Link>
        </div>
        <StatsDashboard />
      </section>

      {/* 바로가기 카드 */}
      <section>
        <h2 className="text-base font-bold mb-4" style={{ color: "var(--text-primary)" }}>
          빠른 메뉴
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <QuickCard
            href="/library/search"
            icon={BookOpen}
            title="책 추가"
            desc="알라딘에서 책을 검색해서 서재에 추가해요"
            color="var(--accent)"
            bg="var(--accent-light)"
            delay={0}
          />
          <QuickCard
            href="/recommendations"
            icon={Star}
            title="AI 추천"
            desc="내 취향 기반으로 새로운 책을 발견해요"
            color="var(--star)"
            bg="#FEF9C3"
            delay={60}
          />
          <QuickCard
            href="/library"
            icon={Library}
            title="내 서재"
            desc="읽은 책, 읽는 중인 책을 한눈에 확인해요"
            color="var(--status-read)"
            bg="var(--status-read-bg)"
            delay={120}
          />
        </div>
      </section>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
   비로그인 랜딩 페이지
───────────────────────────────────────────────────────── */
function LandingHome() {
  return (
    <div className="flex flex-col gap-0">
      {/* 섹션 1: 히어로 */}
      <HeroSection />

      {/* 섹션 1.5: 이런 기능이 있습니다 */}
      <FeaturesSection />

      {/* 섹션 2: 대시보드 소개 */}
      <DashboardSection />

      {/* 섹션 3: 스마트 서재 */}
      <LibrarySection />

      {/* 섹션 4: AI 추천 */}
      <AISection />

      {/* 섹션 4.5: 마이페이지 / 데이터 가져오기 */}
      <MypageSection />

      {/* 섹션 5: CTA */}
      <CTASection />
    </div>
  );
}

/** 섹션 1: 히어로 */
function HeroSection() {
  return (
    <section className="animate-fade-in">
      <div
        className="relative rounded-3xl overflow-hidden px-6 py-14 md:px-14 md:py-20 text-center"
        style={{
          background: "linear-gradient(135deg, #FEF9F4 0%, #FEF3C7 60%, #FFFDF9 100%)",
          border: "1px solid var(--border-default)",
        }}
      >
        {/* 배경 장식 */}
        <div
          className="absolute top-0 right-0 w-80 h-80 rounded-full pointer-events-none"
          style={{
            background: "radial-gradient(circle, rgba(232,160,69,0.18) 0%, transparent 70%)",
            transform: "translate(30%, -30%)",
          }}
        />
        <div
          className="absolute bottom-0 left-0 w-60 h-60 rounded-full pointer-events-none"
          style={{
            background: "radial-gradient(circle, rgba(232,160,69,0.12) 0%, transparent 70%)",
            transform: "translate(-30%, 30%)",
          }}
        />

        <div className="relative flex flex-col items-center gap-6 max-w-xl mx-auto">
          <div
            className="badge"
            style={{ background: "var(--accent-light)", color: "var(--accent-dark)" }}
          >
            <Sparkles size={11} />
            AI 기반 독서 기록 & 추천 서비스
          </div>

          <h1
            className="text-3xl md:text-5xl font-extrabold tracking-tight leading-tight"
            style={{ color: "var(--text-primary)" }}
          >
            내 취향에 딱 맞는<br />
            <span style={{ color: "var(--accent)" }}>책</span>을 찾아드려요
          </h1>

          <p
            className="text-sm md:text-base leading-relaxed max-w-sm"
            style={{ color: "var(--text-secondary)" }}
          >
            독서 기록과 별점을 쌓을수록<br />
            AI가 더 정확하게 당신의 취향을 파악해요.
          </p>

          <Link
            href="/login"
            className="btn-primary px-8 py-3.5"
            style={{ fontSize: "0.9375rem" }}
          >
            <LogIn size={16} />
            Google로 무료 시작하기
            <ArrowRight size={15} />
          </Link>
        </div>
      </div>
    </section>
  );
}

/** 섹션 1.5: 이런 기능이 있습니다 */
function FeaturesSection() {
  const features = [
    {
      icon: TrendingUp,
      title: "독서 통계 & 캘린더",
      desc: "읽은 책, 장르 분포, 월별 현황을 한눈에",
      color: "var(--status-read)",
      bg: "var(--status-read-bg)",
    },
    {
      icon: BookMarked,
      title: "스마트 서재",
      desc: "알라딘 검색, 메모·하이라이트 기록",
      color: "var(--accent-dark)",
      bg: "var(--accent-light)",
    },
    {
      icon: Star,
      title: "AI 맞춤 추천",
      desc: "취향 분석 & 자유로운 질문으로 딱 맞는 책",
      color: "var(--star)",
      bg: "#FEF9C3",
    },
    {
      icon: Upload,
      title: "데이터 가져오기",
      desc: "북적북적 등 다른 앱 기록을 CSV로 한 번에",
      color: "var(--status-reading)",
      bg: "var(--status-reading-bg)",
    },
  ];

  return (
    <section className="py-10 md:py-14">
      <div className="text-center mb-8">
        <p
          className="text-xs font-bold tracking-widest uppercase mb-2"
          style={{ color: "var(--accent-dark)" }}
        >
          Features
        </p>
        <h2
          className="text-xl md:text-2xl font-extrabold"
          style={{ color: "var(--text-primary)" }}
        >
          이런 기능이 있습니다
        </h2>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {features.map(({ icon: Icon, title, desc, color, bg }) => (
          <div key={title} className="card p-5 flex flex-col gap-3">
            <div
              className="w-10 h-10 rounded-2xl flex items-center justify-center"
              style={{ background: bg }}
            >
              <Icon size={18} color={color} strokeWidth={2.5} />
            </div>
            <div>
              <p className="text-sm font-bold mb-1" style={{ color: "var(--text-primary)" }}>
                {title}
              </p>
              <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
                {desc}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/** 섹션 2: 대시보드 소개 */
function DashboardSection() {
  return (
    <section className="py-16 md:py-24">
      <div className="flex flex-col md:flex-row items-center gap-10 md:gap-16">
        {/* 텍스트 */}
        <div className="flex flex-col gap-5 md:w-2/5 order-2 md:order-1">
          <div
            className="badge w-fit"
            style={{ background: "var(--status-read-bg)", color: "var(--status-read)" }}
          >
            <TrendingUp size={11} />
            독서 현황
          </div>
          <h2
            className="text-2xl md:text-3xl font-extrabold leading-snug"
            style={{ color: "var(--text-primary)" }}
          >
            나만의 독서 현황을<br />한눈에 파악하세요.
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            내가 읽은 책의 수, 평균 별점, 선호하는 장르 분포까지.<br />
            독서 캘린더를 통해 매달 나의 독서 습관을 직관적이고
            재미있게 추적할 수 있습니다.
          </p>
        </div>

        {/* 이미지 */}
        <div className="md:w-3/5 order-1 md:order-2">
          <div
            className="rounded-2xl overflow-hidden shadow-lg"
            style={{ border: "1px solid var(--border-default)" }}
          >
            <Image
              src="/captures/home.png"
              alt="독서 대시보드"
              width={800}
              height={500}
              className="w-full h-auto"
              unoptimized
            />
          </div>
        </div>
      </div>
    </section>
  );
}

/** 섹션 3: 스마트 서재 */
function LibrarySection() {
  return (
    <section className="py-16 md:py-24">
      <div className="flex flex-col md:flex-row items-center gap-10 md:gap-16">
        {/* 이미지 그룹 — 겹쳐서 배치 */}
        <div className="md:w-3/5 relative">
          {/* 메인: 내 서재 */}
          <div
            className="rounded-2xl overflow-hidden shadow-lg"
            style={{ border: "1px solid var(--border-default)" }}
          >
            <Image
              src="/captures/library.png"
              alt="내 서재"
              width={800}
              height={500}
              className="w-full h-auto"
              unoptimized
            />
          </div>
          {/* 오버레이: 책 검색 */}
          <div
            className="absolute hidden md:block"
            style={{
              bottom: "-28px",
              right: "-24px",
              width: "52%",
              border: "1.5px solid var(--border-default)",
              borderRadius: "16px",
              overflow: "hidden",
              boxShadow: "0 12px 32px rgba(28,25,23,0.14)",
            }}
          >
            <Image
              src="/captures/book-search.png"
              alt="책 검색"
              width={420}
              height={300}
              className="w-full h-auto"
              unoptimized
            />
          </div>
          {/* 오버레이: 책 상세 */}
          <div
            className="absolute hidden md:block"
            style={{
              top: "-20px",
              right: "-8px",
              width: "38%",
              border: "1.5px solid var(--border-default)",
              borderRadius: "16px",
              overflow: "hidden",
              boxShadow: "0 8px 24px rgba(28,25,23,0.10)",
            }}
          >
            <Image
              src="/captures/book-detail.png"
              alt="책 상세"
              width={320}
              height={240}
              className="w-full h-auto"
              unoptimized
            />
          </div>
          {/* 모바일: 추가 이미지들 */}
          <div className="flex md:hidden gap-2 mt-3">
            <div
              className="flex-1 rounded-xl overflow-hidden"
              style={{ border: "1px solid var(--border-default)" }}
            >
              <Image src="/captures/book-search.png" alt="책 검색" width={300} height={200} className="w-full h-auto" unoptimized />
            </div>
            <div
              className="flex-1 rounded-xl overflow-hidden"
              style={{ border: "1px solid var(--border-default)" }}
            >
              <Image src="/captures/book-detail.png" alt="책 상세" width={300} height={200} className="w-full h-auto" unoptimized />
            </div>
          </div>
        </div>

        {/* 텍스트 */}
        <div className="flex flex-col gap-5 md:w-2/5 mt-8 md:mt-0">
          <div
            className="badge w-fit"
            style={{ background: "var(--accent-light)", color: "var(--accent-dark)" }}
          >
            <BookMarked size={11} />
            스마트 서재
          </div>
          <h2
            className="text-2xl md:text-3xl font-extrabold leading-snug"
            style={{ color: "var(--text-primary)" }}
          >
            기억하고 싶은 문장과<br />감상, 스마트하게 관리하세요.
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            알라딘 검색으로 쉽게 책을 찾고 서재에 추가해 보세요.<br />
            다 읽은 책, 읽고 있는 책을 나누어 보관하고 별점과
            나만의 독서 메모를 남겨 기록을 풍성하게 채울 수 있습니다.
          </p>
        </div>
      </div>
    </section>
  );
}

/** 섹션 4: AI 추천 — 좌측 겹치는 이미지 + 우측 텍스트 */
function AISection() {
  return (
    <section className="py-16 md:py-24">
      <div className="flex flex-col md:flex-row items-center gap-10 md:gap-16">
        {/* 이미지 그룹 — 좌상단 + 우하단 겹치기 */}
        <div
          className="md:w-3/5 relative hidden md:block"
          style={{ paddingBottom: "72px", paddingRight: "28px" }}
        >
          {/* 이미지 1: 취향 기반 추천 (좌상단·뒤) */}
          <div
            className="rounded-2xl overflow-hidden shadow-lg"
            style={{
              border: "1px solid var(--border-default)",
              width: "78%",
            }}
          >
            <Image
              src="/captures/recommend-history.png"
              alt="취향 기반 추천"
              width={600}
              height={420}
              className="w-full h-auto"
              unoptimized
            />
          </div>
          {/* 이미지 2: 질문 기반 추천 (우하단·앞) */}
          <div
            className="absolute"
            style={{
              bottom: 0,
              right: 0,
              width: "68%",
              border: "1.5px solid var(--border-default)",
              borderRadius: "16px",
              overflow: "hidden",
              boxShadow: "0 14px 36px rgba(28,25,23,0.15)",
            }}
          >
            <Image
              src="/captures/recommend-ask.png"
              alt="질문 기반 추천"
              width={520}
              height={360}
              className="w-full h-auto"
              unoptimized
            />
          </div>
        </div>

        {/* 모바일: 두 이미지 나란히 */}
        <div className="flex md:hidden gap-2 w-full">
          <div className="flex-1 rounded-xl overflow-hidden" style={{ border: "1px solid var(--border-default)" }}>
            <Image src="/captures/recommend-history.png" alt="취향 기반 추천" width={300} height={220} className="w-full h-auto" unoptimized />
          </div>
          <div className="flex-1 rounded-xl overflow-hidden" style={{ border: "1px solid var(--border-default)" }}>
            <Image src="/captures/recommend-ask.png" alt="질문 기반 추천" width={300} height={220} className="w-full h-auto" unoptimized />
          </div>
        </div>

        {/* 텍스트 (오른쪽) */}
        <div className="flex flex-col gap-6 md:w-2/5">
          <div
            className="badge w-fit"
            style={{ background: "#FEF9C3", color: "#92400E" }}
          >
            <Star size={11} />
            AI 맞춤 추천
          </div>
          <h2
            className="text-2xl md:text-3xl font-extrabold leading-snug"
            style={{ color: "var(--text-primary)" }}
          >
            나보다 내 취향을<br />더 잘 아는 AI
          </h2>
          <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-2">
              <p className="text-lg md:text-xl font-bold" style={{ color: "var(--text-primary)" }}>
                ✨ 취향 기반 추천
              </p>
              <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                서재에 쌓인 독서 기록과 별점을 바탕으로,
                내 취향에 딱 맞는 새로운 책을 발견해 보세요.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <p className="text-lg md:text-xl font-bold" style={{ color: "var(--text-primary)" }}>
                💬 질문 기반 추천
              </p>
              <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                "요즘 MZ 시인의 시집 추천해 줘"처럼
                원하는 분위기를 말하기만 하면 AI가 찰떡같이 찾아드립니다.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/** 섹션 4.5: 마이페이지 / 데이터 가져오기 */
function MypageSection() {
  return (
    <section className="py-16 md:py-24">
      <div className="flex flex-col md:flex-row items-center gap-10 md:gap-16">
        {/* 텍스트 (왼쪽) */}
        <div className="flex flex-col gap-5 md:w-2/5 order-2 md:order-1">
          <div
            className="badge w-fit"
            style={{ background: "var(--status-reading-bg)", color: "var(--status-reading)" }}
          >
            <Upload size={11} />
            데이터 이전
          </div>
          <h2
            className="text-2xl md:text-3xl font-extrabold leading-snug"
            style={{ color: "var(--text-primary)" }}
          >
            다른 앱의 독서 기록,<br />쉽게 옮겨오세요.
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
            북적북적 등 다른 독서 앱에서 사용하던 기록을
            CSV 파일 하나로 간편하게 가져올 수 있어요.<br />
            소중한 독서 이력을 처음부터 다시 입력할 필요가 없습니다.
          </p>
        </div>

        {/* 이미지 (오른쪽) */}
        <div className="md:w-3/5 order-1 md:order-2">
          <div
            className="rounded-2xl overflow-hidden shadow-lg"
            style={{ border: "1px solid var(--border-default)" }}
          >
            <Image
              src="/captures/mypage.png"
              alt="마이페이지 데이터 가져오기"
              width={800}
              height={500}
              className="w-full h-auto"
              unoptimized
            />
          </div>
        </div>
      </div>
    </section>
  );
}

/** 섹션 5: CTA — 밝은 크림 배너 */
function CTASection() {
  return (
    <section className="py-10 md:py-14">
      <div
        className="relative rounded-3xl overflow-hidden px-6 py-14 md:px-14 md:py-16 text-center"
        style={{
          background: "linear-gradient(135deg, #FEF9F4 0%, #FEF3C7 50%, #FEF9F4 100%)",
          border: "1px solid var(--border-default)",
        }}
      >
        {/* 배경 장식 */}
        <div
          className="absolute top-0 right-0 w-64 h-64 rounded-full pointer-events-none"
          style={{
            background: "radial-gradient(circle, rgba(232,160,69,0.14) 0%, transparent 70%)",
            transform: "translate(30%, -30%)",
          }}
        />
        <div
          className="absolute bottom-0 left-0 w-48 h-48 rounded-full pointer-events-none"
          style={{
            background: "radial-gradient(circle, rgba(232,160,69,0.10) 0%, transparent 70%)",
            transform: "translate(-30%, 30%)",
          }}
        />

        <div className="relative flex flex-col items-center gap-5">
          {/* Sparkles 아이콘 */}
          <div
            className="w-12 h-12 rounded-2xl flex items-center justify-center"
            style={{ background: "var(--accent-light)" }}
          >
            <Sparkles size={22} color="#E8A045" strokeWidth={2} />
          </div>

          <div className="flex flex-col gap-2">
            <h2
              className="text-2xl md:text-3xl font-extrabold leading-snug"
              style={{ color: "var(--text-primary)" }}
            >
              지금 바로 북치기박치기에서<br />인생 책을 만나보세요.
            </h2>
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              Google 계정으로 5초만에 가입 · 완전 무료
            </p>
          </div>

          <Link
            href="/login"
            className="btn-primary px-8 py-3.5 mt-1"
            style={{ fontSize: "0.9375rem" }}
          >
            <LogIn size={16} />
            Google로 무료 시작하기
          </Link>
        </div>
      </div>
    </section>
  );
}

/* ─────────────────────────────────────────────────────────
   공유 컴포넌트
───────────────────────────────────────────────────────── */
function QuickCard({
  href,
  icon: Icon,
  title,
  desc,
  color,
  bg,
  delay,
}: {
  href: string;
  icon: typeof BookOpen;
  title: string;
  desc: string;
  color: string;
  bg: string;
  delay: number;
}) {
  return (
    <Link
      href={href}
      className="card p-5 flex flex-col gap-3 cursor-pointer animate-fade-in"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div
        className="w-10 h-10 rounded-2xl flex items-center justify-center"
        style={{ background: bg }}
      >
        <Icon size={18} color={color} strokeWidth={2.5} />
      </div>
      <div>
        <p className="text-sm font-bold mb-1" style={{ color: "var(--text-primary)" }}>
          {title}
        </p>
        <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
          {desc}
        </p>
      </div>
      <div className="flex items-center gap-1 mt-auto" style={{ color }}>
        <span className="text-xs font-semibold">바로가기</span>
        <ArrowRight size={12} />
      </div>
    </Link>
  );
}

/* ─────────────────────────────────────────────────────────
   메인 export
───────────────────────────────────────────────────────── */
/** 홈 페이지 콘텐츠 — 로그인 상태에 따라 다른 화면 */
export default function HomeContent() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex flex-col gap-8">
        <div
          className="rounded-3xl animate-pulse"
          style={{ height: "200px", background: "var(--bg-subtle)" }}
        />
      </div>
    );
  }

  if (user) {
    return <LoggedInHome name={user.name || user.email} />;
  }

  return <LandingHome />;
}
