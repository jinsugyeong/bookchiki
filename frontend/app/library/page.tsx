"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Plus, Search, SlidersHorizontal, BookOpen } from "lucide-react";
import { getMyBooks } from "@/lib/api";
import type { UserBook } from "@/lib/types";
import BookCard from "@/components/library/BookCard";
import BookDetailModal from "@/components/library/BookDetailModal";
import { PageLoading, SkeletonCard } from "@/components/ui/LoadingSpinner";
import { useRequireAuth } from "@/hooks/useRequireAuth";

const STATUS_FILTERS = [
  { value: "", label: "전체" },
  { value: "read", label: "읽은 책" },
  { value: "reading", label: "읽고 있는 책" },
  { value: "wishlist", label: "읽고 싶은 책" },
] as const;

const SORT_OPTIONS = [
  { value: "newest", label: "최근 추가순" },
  { value: "oldest", label: "오래된 순" },
  { value: "rating", label: "별점 높은 순" },
  { value: "title", label: "제목 가나다순" },
] as const;

const PAGE_SIZE = 20;

/** 내 서재 페이지 */
export default function LibraryPage() {
  const { user, isLoading: authLoading } = useRequireAuth();
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [sortBy, setSortBy] = useState<string>("newest");
  const [search, setSearch] = useState("");
  const [selectedBook, setSelectedBook] = useState<UserBook | null>(null);
  const [page, setPage] = useState(1);

  // 전체 목록을 한 번만 fetch해서 탭 개수 + 필터링에 재사용
  // hooks는 early return 전에 선언해야 함 (Rules of Hooks)
  const { data: allBooks, isLoading } = useQuery({
    queryKey: ["myBooks"],
    queryFn: () => getMyBooks({ limit: 500 }),
    enabled: !!user,
  });

  if (authLoading) return <PageLoading />;
  if (!user) return null;

  const books = statusFilter
    ? (allBooks ?? []).filter((ub) => ub.status === statusFilter)
    : (allBooks ?? []);

  const countByStatus = {
    "": allBooks?.length ?? 0,
    read: (allBooks ?? []).filter((ub) => ub.status === "read").length,
    reading: (allBooks ?? []).filter((ub) => ub.status === "reading").length,
    wishlist: (allBooks ?? []).filter((ub) => ub.status === "wishlist").length,
  };

  /** 검색 + 정렬 필터링 */
  const filteredBooks = (books ?? [])
    .filter((ub) => {
      if (!search) return true;
      const q = search.toLowerCase();
      return (
        ub.book.title.toLowerCase().includes(q) ||
        ub.book.author.toLowerCase().includes(q)
      );
    })
    .sort((a, b) => {
      switch (sortBy) {
        case "oldest":
          return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
        case "rating":
          return (b.rating ?? 0) - (a.rating ?? 0);
        case "title":
          return a.book.title.localeCompare(b.book.title, "ko");
        default: // newest
          return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      }
    });

  const totalPages = Math.ceil(filteredBooks.length / PAGE_SIZE);
  const pagedBooks = filteredBooks.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div className="flex flex-col gap-5">
      {/* 페이지 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-extrabold" style={{ color: "var(--text-primary)" }}>
            내 서재
          </h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--text-muted)" }}>
            {books?.length ?? 0}권의 책이 있어요
          </p>
        </div>
        <Link href="/library/search" className="btn-primary text-sm">
          <Plus size={15} />
          책 추가
        </Link>
      </div>

      {/* 검색 + 정렬 */}
      <div className="flex flex-col sm:flex-row gap-2">
        {/* 검색 */}
        <div className="relative flex-1">
          <Search
            size={15}
            className="absolute left-3 top-1/2 -translate-y-1/2"
            style={{ color: "var(--text-muted)" }}
          />
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="제목이나 저자 검색..."
            className="w-full pl-9 pr-4 py-2.5 rounded-xl text-sm"
            style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border-default)",
              color: "var(--text-primary)",
              outline: "none",
            }}
            onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
            onBlur={(e) => (e.target.style.borderColor = "var(--border-default)")}
          />
        </div>

        {/* 정렬 */}
        <div className="flex items-center gap-2">
          <SlidersHorizontal size={15} style={{ color: "var(--text-muted)" }} />
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="text-sm rounded-xl px-3 py-2.5 cursor-pointer"
            style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border-default)",
              color: "var(--text-secondary)",
              outline: "none",
            }}
          >
            {SORT_OPTIONS.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 상태 필터 탭 */}
      <div className="flex gap-1.5 overflow-x-auto pb-1">
        {STATUS_FILTERS.map(({ value, label }) => {
          const count = countByStatus[value as keyof typeof countByStatus];
          return (
            <button
              key={value}
              type="button"
              onClick={() => { setStatusFilter(value); setPage(1); }}
              className="flex-shrink-0 flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer"
              style={{
                background: statusFilter === value ? "var(--accent)" : "var(--bg-card)",
                color: statusFilter === value ? "white" : "var(--text-secondary)",
                border: "1px solid",
                borderColor: statusFilter === value ? "var(--accent)" : "var(--border-default)",
              }}
            >
              {label}
              {count > 0 && (
                <span
                  className="text-xs font-bold px-1.5 py-0.5 rounded-full leading-none"
                  style={{
                    background: statusFilter === value ? "rgba(255,255,255,0.25)" : "var(--bg-subtle)",
                    color: statusFilter === value ? "white" : "var(--text-muted)",
                  }}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* 책 목록 */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[...Array(6)].map((_, i) => (
            <SkeletonCard key={i} className="h-32" />
          ))}
        </div>
      ) : filteredBooks.length === 0 ? (
        <div
          className="flex flex-col items-center justify-center gap-4 py-20 rounded-3xl"
          style={{ background: "var(--bg-subtle)", border: "1px solid var(--border-default)" }}
        >
          <div
            className="w-14 h-14 rounded-2xl flex items-center justify-center"
            style={{ background: "var(--accent-light)" }}
          >
            <BookOpen size={24} style={{ color: "var(--accent)" }} />
          </div>
          <div className="text-center">
            <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              {search ? "검색 결과가 없어요" : "아직 책이 없어요"}
            </p>
            <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
              {search ? "다른 검색어로 찾아보세요" : "첫 번째 책을 추가해보세요!"}
            </p>
          </div>
          {!search && (
            <Link href="/library/search" className="btn-primary text-sm">
              <Plus size={14} />
              책 추가하기
            </Link>
          )}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {pagedBooks.map((ub, idx) => (
              <div
                key={ub.id}
                className="animate-fade-in"
                style={{ animationDelay: `${idx * 30}ms` }}
              >
                <BookCard userBook={ub} onClick={() => setSelectedBook(ub)} />
              </div>
            ))}
          </div>

          {/* 페이지네이션 */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 pt-2">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 rounded-xl text-xs font-medium transition-all cursor-pointer"
                style={{
                  background: page === 1 ? "var(--bg-subtle)" : "var(--bg-card)",
                  color: page === 1 ? "var(--border-default)" : "var(--text-secondary)",
                  border: "1px solid var(--border-default)",
                  cursor: page === 1 ? "not-allowed" : "pointer",
                }}
              >
                이전
              </button>
              {Array.from({ length: totalPages }, (_, i) => i + 1)
                .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 2)
                .reduce<(number | "...")[]>((acc, p, i, arr) => {
                  if (i > 0 && typeof arr[i - 1] === "number" && (p as number) - (arr[i - 1] as number) > 1) acc.push("...");
                  acc.push(p);
                  return acc;
                }, [])
                .map((p, i) =>
                  p === "..." ? (
                    <span key={`ellipsis-${i}`} className="text-xs px-1" style={{ color: "var(--text-muted)" }}>…</span>
                  ) : (
                    <button
                      key={p}
                      type="button"
                      onClick={() => setPage(p as number)}
                      className="w-8 h-8 rounded-xl text-xs font-medium transition-all cursor-pointer"
                      style={{
                        background: page === p ? "var(--accent)" : "var(--bg-card)",
                        color: page === p ? "white" : "var(--text-secondary)",
                        border: "1px solid",
                        borderColor: page === p ? "var(--accent)" : "var(--border-default)",
                      }}
                    >
                      {p}
                    </button>
                  )
                )}
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-3 py-1.5 rounded-xl text-xs font-medium transition-all cursor-pointer"
                style={{
                  background: page === totalPages ? "var(--bg-subtle)" : "var(--bg-card)",
                  color: page === totalPages ? "var(--border-default)" : "var(--text-secondary)",
                  border: "1px solid var(--border-default)",
                  cursor: page === totalPages ? "not-allowed" : "pointer",
                }}
              >
                다음
              </button>
            </div>
          )}
        </>
      )}

      {/* 책 상세 모달 */}
      {selectedBook && (
        <BookDetailModal
          userBook={selectedBook}
          onClose={() => setSelectedBook(null)}
        />
      )}
    </div>
  );
}
