"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getMyStats, getMyBooks } from "@/lib/api";
import type { UserBook } from "@/lib/types";
import { BookOpen, CheckCircle, Star, ChevronLeft, ChevronRight } from "lucide-react";
import { SkeletonCard } from "@/components/ui/LoadingSpinner";
import Image from "next/image";

/** 통계 카드 하나 */
function StatCard({
  label,
  value,
  icon: Icon,
  color,
  bg,
  delay = 0,
}: {
  label: string;
  value: string | number;
  icon: typeof BookOpen;
  color: string;
  bg: string;
  delay?: number;
}) {
  return (
    <div
      className="card p-4 flex items-center gap-3 animate-fade-in"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div
        className="w-10 h-10 rounded-2xl flex items-center justify-center flex-shrink-0"
        style={{ background: bg }}
      >
        <Icon size={18} color={color} strokeWidth={2.5} />
      </div>
      <div>
        <p className="text-xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
          {value}
        </p>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          {label}
        </p>
      </div>
    </div>
  );
}

/** 장르 분포 도넛 차트 */
function DonutChart({ distribution }: { distribution: Record<string, number> }) {
  const entries = Object.entries(distribution)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 6);

  const total = entries.reduce((s, [, v]) => s + v, 0);

  const COLORS = [
    "#E8A045",
    "#22C55E",
    "#3B82F6",
    "#A855F7",
    "#F97316",
    "#06B6D4",
  ];

  if (total === 0) return null;

  // SVG 도넛 계산
  const cx = 60;
  const cy = 60;
  const r = 40;
  const strokeWidth = 22;
  const circumference = 2 * Math.PI * r;

  let cumulativePercent = 0;
  const segments = entries.map(([genre, count], idx) => {
    const percent = count / total;
    const offset = circumference * (1 - cumulativePercent);
    const dash = circumference * percent;
    cumulativePercent += percent;
    return { genre, count, percent, offset, dash, color: COLORS[idx % COLORS.length] };
  });

  return (
    <div className="flex items-center gap-4">
      {/* 도넛 SVG */}
      <div className="flex-shrink-0">
        <svg width="120" height="120" viewBox="0 0 120 120">
          {/* 배경 원 */}
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke="var(--bg-subtle)"
            strokeWidth={strokeWidth}
          />
          {/* 세그먼트 */}
          {segments.map(({ genre, offset, dash, color }) => (
            <circle
              key={genre}
              cx={cx}
              cy={cy}
              r={r}
              fill="none"
              stroke={color}
              strokeWidth={strokeWidth}
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={offset}
              transform={`rotate(-90 ${cx} ${cy})`}
              style={{ transition: "stroke-dasharray 0.5s ease" }}
            />
          ))}
          {/* 중앙 텍스트 */}
          <text x={cx} y={cy - 4} textAnchor="middle" fontSize="18" fontWeight="700" fill="var(--text-primary)">
            {total}
          </text>
          <text x={cx} y={cy + 13} textAnchor="middle" fontSize="9" fill="var(--text-muted)">
            권
          </text>
        </svg>
      </div>

      {/* 범례 */}
      <div className="flex flex-col gap-1.5 min-w-0 flex-1">
        {segments.map(({ genre, count, percent, color }) => (
          <div key={genre} className="flex items-center gap-2">
            <div
              className="flex-shrink-0 w-2.5 h-2.5 rounded-full"
              style={{ background: color }}
            />
            <span
              className="text-xs truncate flex-1"
              style={{ color: "var(--text-secondary)" }}
            >
              {genre}
            </span>
            <span className="text-xs flex-shrink-0 tabular-nums" style={{ color: "var(--text-muted)" }}>
              {count} ({Math.round(percent * 100)}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** 독서 캘린더 — 월별 다읽은 책 표시 */
function ReadingCalendar({ readBooks }: { readBooks: UserBook[] }) {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth()); // 0-indexed

  const goToPrev = () => {
    if (month === 0) { setYear((y) => y - 1); setMonth(11); }
    else setMonth((m) => m - 1);
  };

  const goToNext = () => {
    const nextYear = month === 11 ? year + 1 : year;
    const nextMonth = month === 11 ? 0 : month + 1;
    if (nextYear > now.getFullYear() || (nextYear === now.getFullYear() && nextMonth > now.getMonth())) return;
    if (month === 11) { setYear((y) => y + 1); setMonth(0); }
    else setMonth((m) => m + 1);
  };

  const isNextDisabled =
    year > now.getFullYear() ||
    (year === now.getFullYear() && month >= now.getMonth());

  // 이 달의 일수 + 시작 요일
  const firstDay = new Date(year, month, 1).getDay(); // 0=Sun
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  // 이 달에 다 읽은 책 → 날짜별 목록
  const booksByDay: Record<number, UserBook[]> = {};
  readBooks.forEach((ub) => {
    const dt = ub.finished_at || ub.created_at;
    if (!dt) return;
    const d = new Date(dt);
    if (d.getFullYear() === year && d.getMonth() === month) {
      const day = d.getDate();
      if (!booksByDay[day]) booksByDay[day] = [];
      booksByDay[day].push(ub);
    }
  });

  const MONTH_NAMES = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"];
  const DAY_NAMES = ["일", "월", "화", "수", "목", "금", "토"];

  return (
    <div className="flex flex-col gap-3">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
          {year}년 {MONTH_NAMES[month]}
        </span>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={goToPrev}
            className="p-1 rounded-lg transition-colors cursor-pointer"
            style={{ color: "var(--text-muted)", background: "var(--bg-subtle)" }}
          >
            <ChevronLeft size={14} />
          </button>
          <button
            type="button"
            onClick={goToNext}
            disabled={isNextDisabled}
            className="p-1 rounded-lg transition-colors cursor-pointer"
            style={{
              color: isNextDisabled ? "var(--border-default)" : "var(--text-muted)",
              background: "var(--bg-subtle)",
            }}
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {/* 요일 헤더 */}
      <div className="grid grid-cols-7 gap-0.5">
        {DAY_NAMES.map((d) => (
          <div
            key={d}
            className="text-center text-[10px] font-semibold py-1"
            style={{ color: "var(--text-muted)" }}
          >
            {d}
          </div>
        ))}
      </div>

      {/* 날짜 그리드 */}
      <div className="grid grid-cols-7 gap-0.5">
        {/* 빈 칸 (시작 요일 전) */}
        {Array.from({ length: firstDay }, (_, i) => (
          <div key={`empty-${i}`} />
        ))}

        {/* 날짜 셀 */}
        {Array.from({ length: daysInMonth }, (_, i) => {
          const day = i + 1;
          const dayBooks = booksByDay[day] ?? [];
          const hasBooks = dayBooks.length > 0;

          return (
            <div
              key={day}
              className="relative flex flex-col items-center gap-0.5 rounded-lg py-1"
              style={{
                background: hasBooks ? "var(--accent-light)" : "transparent",
                minHeight: "36px",
              }}
            >
              <span
                className="text-[10px] font-medium"
                style={{ color: hasBooks ? "var(--accent-dark)" : "var(--text-muted)" }}
              >
                {day}
              </span>
              {hasBooks && (
                <div className="flex gap-px justify-center flex-wrap px-0.5">
                  {dayBooks.slice(0, 2).map((ub) => (
                    <div
                      key={ub.id}
                      className="rounded overflow-hidden flex-shrink-0"
                      style={{ width: "18px", height: "24px", background: "var(--bg-subtle)" }}
                      title={ub.book.title}
                    >
                      {ub.book.cover_image_url ? (
                        <Image
                          src={ub.book.cover_image_url}
                          alt={ub.book.title}
                          width={18}
                          height={24}
                          className="w-full h-full object-cover"
                          unoptimized
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <BookOpen size={8} style={{ color: "var(--text-muted)" }} />
                        </div>
                      )}
                    </div>
                  ))}
                  {dayBooks.length > 2 && (
                    <div
                      className="text-[8px] font-bold flex items-center justify-center rounded"
                      style={{ width: "18px", height: "24px", background: "var(--accent)", color: "white" }}
                    >
                      +{dayBooks.length - 2}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 이 달의 독서 합계 */}
      {(() => {
        const monthTotal = Object.values(booksByDay).reduce((s, arr) => s + arr.length, 0);
        return monthTotal > 0 ? (
          <p className="text-xs text-center" style={{ color: "var(--text-muted)" }}>
            이번 달 <strong style={{ color: "var(--accent-dark)" }}>{monthTotal}권</strong> 완독
          </p>
        ) : (
          <p className="text-xs text-center" style={{ color: "var(--text-muted)" }}>
            이번 달 완독 기록이 없어요
          </p>
        );
      })()}
    </div>
  );
}

/** 월별 독서 통계 바 차트 */
function MonthlyStats({ monthlyCounts }: { monthlyCounts: Record<string, number> }) {
  // 최근 12개월 데이터만 표시
  const entries = Object.entries(monthlyCounts)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(-12);

  if (entries.length === 0) return null;

  const maxCount = Math.max(...entries.map(([, v]) => v), 1);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-end gap-1.5 h-24">
        {entries.map(([month, count]) => {
          const heightPct = (count / maxCount) * 100;
          const label = month.slice(5); // "MM" 부분만
          return (
            <div key={month} className="flex flex-col items-center gap-1 flex-1 min-w-0">
              <span
                className="text-[10px] font-semibold tabular-nums"
                style={{ color: count > 0 ? "var(--accent-dark)" : "transparent" }}
              >
                {count > 0 ? count : ""}
              </span>
              <div
                className="w-full rounded-t-lg transition-all"
                style={{
                  height: `${Math.max(heightPct, count > 0 ? 8 : 2)}%`,
                  background: count > 0 ? "var(--accent)" : "var(--bg-subtle)",
                  minHeight: count > 0 ? "8px" : "2px",
                }}
              />
              <span
                className="text-[9px] tabular-nums"
                style={{ color: "var(--text-muted)" }}
              >
                {label}월
              </span>
            </div>
          );
        })}
      </div>
      <p className="text-[11px] text-center" style={{ color: "var(--text-muted)" }}>
        총{" "}
        <strong style={{ color: "var(--accent-dark)" }}>
          {entries.reduce((s, [, v]) => s + v, 0)}권
        </strong>{" "}
        완독
      </p>
    </div>
  );
}

/** 독서 통계 대시보드 */
export default function StatsDashboard() {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["myStats"],
    queryFn: getMyStats,
  });

  const { data: readBooks, isLoading: booksLoading } = useQuery<UserBook[]>({
    queryKey: ["myBooks", "read"],
    queryFn: () => getMyBooks({ status: "read", limit: 200 }),
  });

  const isLoading = statsLoading || booksLoading;

  if (isLoading) {
    return (
      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[...Array(4)].map((_, i) => (
            <SkeletonCard key={i} className="h-20" />
          ))}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="flex flex-col gap-3">
            <SkeletonCard className="h-48" />
            <SkeletonCard className="h-32" />
          </div>
          <SkeletonCard className="h-80" />
        </div>
      </div>
    );
  }

  if (!stats) return null;

  const hasGenres = Object.keys(stats.genre_distribution || {}).length > 0;

  return (
    <div className="flex flex-col gap-4">
      {/* 숫자 통계 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard
          label="전체 도서"
          value={stats.total_books}
          icon={BookOpen}
          color="var(--accent-dark)"
          bg="var(--accent-light)"
          delay={0}
        />
        <StatCard
          label="읽은 책"
          value={stats.books_read}
          icon={CheckCircle}
          color="var(--status-read)"
          bg="var(--status-read-bg)"
          delay={60}
        />
        <StatCard
          label="읽고 있는 책"
          value={stats.books_reading}
          icon={BookOpen}
          color="var(--status-reading)"
          bg="var(--status-reading-bg)"
          delay={120}
        />
        <StatCard
          label="평균 별점"
          value={stats.average_rating ? stats.average_rating.toFixed(1) : "—"}
          icon={Star}
          color="var(--star)"
          bg="#FEF9C3"
          delay={180}
        />
      </div>

      {/* 왼쪽: 장르분포 + 월별통계 / 오른쪽: 독서캘린더 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* 왼쪽 열 */}
        <div className="flex flex-col gap-3">
          {hasGenres && (
            <div className="card p-5 animate-fade-in" style={{ animationDelay: "240ms" }}>
              <p className="text-sm font-semibold mb-4" style={{ color: "var(--text-primary)" }}>
                장르 분포
              </p>
              <DonutChart distribution={stats.genre_distribution} />
            </div>
          )}
          {Object.keys(stats.monthly_counts || {}).length > 0 && (
            <div className="card p-5 animate-fade-in" style={{ animationDelay: "300ms" }}>
              <p className="text-sm font-semibold mb-4" style={{ color: "var(--text-primary)" }}>
                월별 독서 통계
              </p>
              <MonthlyStats monthlyCounts={stats.monthly_counts} />
            </div>
          )}
        </div>

        {/* 오른쪽 열: 독서 캘린더 */}
        <div className="card p-5 animate-fade-in" style={{ animationDelay: "360ms" }}>
          <p className="text-sm font-semibold mb-3" style={{ color: "var(--text-primary)" }}>
            독서 캘린더
          </p>
          <ReadingCalendar readBooks={readBooks ?? []} />
        </div>
      </div>
    </div>
  );
}
