"use client";

import { useState } from "react";
import Image from "next/image";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Plus, BookOpen, Check, ArrowLeft, RotateCcw } from "lucide-react";
import Link from "next/link";
import { searchAladin, deleteUserBook } from "@/lib/api";
import type { AladinBook, UserBook } from "@/lib/types";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import { PageLoading } from "@/components/ui/LoadingSpinner";
import AddToLibraryModal from "@/components/library/AddToLibraryModal";
import { useRequireAuth } from "@/hooks/useRequireAuth";

const SEARCH_PAGE_SIZE = 10;

/** 책 검색 페이지 (알라딘 API) */
export default function LibrarySearchPage() {
  const { user, isLoading: authLoading } = useRequireAuth();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<AladinBook[]>([]);
  /** key → userBookId 매핑 (취소용 ID 보존) */
  const [addedMap, setAddedMap] = useState<Map<string, string>>(new Map());
  const [undoingKey, setUndoingKey] = useState<string | null>(null);
  const [modalBook, setModalBook] = useState<AladinBook | null>(null);
  const [searchPage, setSearchPage] = useState(1);

  if (authLoading) return <PageLoading />;
  if (!user) return null;

  const searchMutation = useMutation({
    mutationFn: () => searchAladin(query, 20),
    onSuccess: (data) => { setResults(data); setSearchPage(1); },
  });

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) searchMutation.mutate();
  };

  const getBookKey = (book: AladinBook) => book.isbn || `${book.title}::${book.author}`;

  const handleAddSuccess = (userBook: UserBook) => {
    if (modalBook) {
      const key = getBookKey(modalBook);
      setAddedMap((prev) => new Map(prev).set(key, userBook.id));
      queryClient.invalidateQueries({ queryKey: ["myBooks"] });
      queryClient.invalidateQueries({ queryKey: ["myStats"] });
    }
    setModalBook(null);
  };

  const handleUndo = async (key: string) => {
    const userBookId = addedMap.get(key);
    if (!userBookId) return;

    setUndoingKey(key);
    try {
      await deleteUserBook(userBookId);
      setAddedMap((prev) => {
        const next = new Map(prev);
        next.delete(key);
        return next;
      });
      queryClient.invalidateQueries({ queryKey: ["myBooks"] });
      queryClient.invalidateQueries({ queryKey: ["myStats"] });
    } finally {
      setUndoingKey(null);
    }
  };

  return (
    <div className="flex flex-col gap-5 max-w-2xl mx-auto">
      {/* 헤더 */}
      <div className="flex items-center gap-3">
        <Link
          href="/library"
          className="p-2 rounded-xl transition-colors cursor-pointer"
          style={{ color: "var(--text-muted)", background: "var(--bg-card)", border: "1px solid var(--border-default)" }}
        >
          <ArrowLeft size={18} />
        </Link>
        <div>
          <h1 className="text-xl font-extrabold" style={{ color: "var(--text-primary)" }}>
            책 검색
          </h1>
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            알라딘에서 책을 검색해서 서재에 추가해요
          </p>
        </div>
      </div>

      {/* 검색 폼 */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search
            size={16}
            className="absolute left-3.5 top-1/2 -translate-y-1/2"
            style={{ color: "var(--text-muted)" }}
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="책 제목, 저자, ISBN으로 검색..."
            className="w-full pl-10 pr-4 py-3 rounded-xl text-sm"
            style={{
              background: "var(--bg-card)",
              border: "1px solid var(--border-default)",
              color: "var(--text-primary)",
              outline: "none",
            }}
            onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
            onBlur={(e) => (e.target.style.borderColor = "var(--border-default)")}
            autoFocus
          />
        </div>
        <button
          type="submit"
          disabled={!query.trim() || searchMutation.isPending}
          className="btn-primary"
        >
          {searchMutation.isPending ? <LoadingSpinner size={16} /> : <Search size={16} />}
          검색
        </button>
      </form>

      {/* 검색 중 */}
      {searchMutation.isPending && (
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-3">
            <LoadingSpinner size={32} />
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              책을 찾고 있어요...
            </p>
          </div>
        </div>
      )}

      {/* 검색 결과 */}
      {!searchMutation.isPending && results.length > 0 && (
        <div className="flex flex-col gap-3">
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            {results.length}개의 결과
          </p>
          {results.slice((searchPage - 1) * SEARCH_PAGE_SIZE, searchPage * SEARCH_PAGE_SIZE).map((book) => {
            const key = getBookKey(book);
            const isAdded = addedMap.has(key);
            const isUndoing = undoingKey === key;

            return (
              <div
                key={key}
                className="card p-4 flex gap-3 items-start animate-fade-in transition-all"
                onClick={() => !isAdded && setModalBook(book)}
                style={{ cursor: isAdded ? "default" : "pointer" }}
              >
                {/* 표지 */}
                <div
                  className="flex-shrink-0 rounded-xl overflow-hidden"
                  style={{
                    width: "56px",
                    height: "78px",
                    background: "var(--bg-subtle)",
                    border: "1px solid var(--border-default)",
                  }}
                >
                  {book.cover_image_url ? (
                    <Image
                      src={book.cover_image_url}
                      alt={book.title}
                      width={56}
                      height={78}
                      className="w-full h-full object-cover"
                      unoptimized
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <BookOpen size={18} style={{ color: "var(--text-muted)" }} />
                    </div>
                  )}
                </div>

                {/* 텍스트 */}
                <div className="flex-1 min-w-0">
                  <h3
                    className="text-sm font-bold leading-snug line-clamp-2"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {book.title}
                  </h3>
                  <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                    {book.author}
                  </p>
                  <div className="flex flex-wrap gap-1 items-center mt-0.5">
                    {book.publisher && (
                      <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                        {book.publisher}
                      </span>
                    )}
                    {book.publisher && book.published_at && (
                      <span className="text-[11px]" style={{ color: "var(--border-default)" }}>·</span>
                    )}
                    {book.published_at && (
                      <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                        {book.published_at.slice(0, 7)}
                      </span>
                    )}
                  </div>
                  {book.genre && (
                    <span
                      className="badge text-[11px] mt-1"
                      style={{ background: "var(--accent-light)", color: "var(--accent-dark)" }}
                    >
                      {book.genre}
                    </span>
                  )}
                  {book.description && (
                    <p
                      className="text-xs mt-1.5 line-clamp-2"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      {book.description}
                    </p>
                  )}
                </div>

                {/* 추가/취소 버튼 */}
                {isAdded ? (
                  <div className="flex-shrink-0 flex flex-col items-end gap-1">
                    <div
                      className="flex items-center gap-1 px-3 py-2 rounded-xl text-xs font-semibold"
                      style={{
                        background: "var(--status-read-bg)",
                        color: "var(--status-read)",
                      }}
                    >
                      <Check size={13} />
                      추가됨
                    </div>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); handleUndo(key); }}
                      disabled={isUndoing}
                      className="flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium transition-colors cursor-pointer"
                      style={{
                        color: "var(--text-muted)",
                        background: "var(--bg-subtle)",
                        border: "1px solid var(--border-default)",
                      }}
                    >
                      {isUndoing ? <LoadingSpinner size={10} /> : <RotateCcw size={10} />}
                      취소
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setModalBook(book);
                    }}
                    className="flex-shrink-0 flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer"
                    style={{
                      background: "var(--accent)",
                      color: "white",
                      border: "none",
                    }}
                  >
                    <Plus size={13} />
                    추가
                  </button>
                )}
              </div>
            );
          })}

          {/* 검색 페이지네이션 */}
          {Math.ceil(results.length / SEARCH_PAGE_SIZE) > 1 && (
            <div className="flex items-center justify-center gap-2 pt-1">
              <button
                type="button"
                onClick={() => setSearchPage((p) => Math.max(1, p - 1))}
                disabled={searchPage === 1}
                className="px-3 py-1.5 rounded-xl text-xs font-medium transition-all"
                style={{
                  background: searchPage === 1 ? "var(--bg-subtle)" : "var(--bg-card)",
                  color: searchPage === 1 ? "var(--border-default)" : "var(--text-secondary)",
                  border: "1px solid var(--border-default)",
                  cursor: searchPage === 1 ? "not-allowed" : "pointer",
                }}
              >
                이전
              </button>
              {Array.from({ length: Math.ceil(results.length / SEARCH_PAGE_SIZE) }, (_, i) => i + 1).map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setSearchPage(p)}
                  className="w-8 h-8 rounded-xl text-xs font-medium transition-all"
                  style={{
                    background: searchPage === p ? "var(--accent)" : "var(--bg-card)",
                    color: searchPage === p ? "white" : "var(--text-secondary)",
                    border: "1px solid",
                    borderColor: searchPage === p ? "var(--accent)" : "var(--border-default)",
                    cursor: "pointer",
                  }}
                >
                  {p}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setSearchPage((p) => Math.min(Math.ceil(results.length / SEARCH_PAGE_SIZE), p + 1))}
                disabled={searchPage === Math.ceil(results.length / SEARCH_PAGE_SIZE)}
                className="px-3 py-1.5 rounded-xl text-xs font-medium transition-all"
                style={{
                  background: searchPage === Math.ceil(results.length / SEARCH_PAGE_SIZE) ? "var(--bg-subtle)" : "var(--bg-card)",
                  color: searchPage === Math.ceil(results.length / SEARCH_PAGE_SIZE) ? "var(--border-default)" : "var(--text-secondary)",
                  border: "1px solid var(--border-default)",
                  cursor: searchPage === Math.ceil(results.length / SEARCH_PAGE_SIZE) ? "not-allowed" : "pointer",
                }}
              >
                다음
              </button>
            </div>
          )}
        </div>
      )}

      {/* 결과 없음 */}
      {!searchMutation.isPending && results.length === 0 && searchMutation.isSuccess && (
        <div
          className="flex flex-col items-center gap-3 py-16 rounded-3xl"
          style={{ background: "var(--bg-subtle)", border: "1px solid var(--border-default)" }}
        >
          <BookOpen size={32} style={{ color: "var(--text-muted)" }} />
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            검색 결과가 없어요
          </p>
        </div>
      )}

      {/* 초기 상태 */}
      {!searchMutation.isSuccess && !searchMutation.isPending && (
        <div
          className="flex flex-col items-center gap-3 py-16 rounded-3xl"
          style={{ background: "var(--bg-subtle)", border: "1px solid var(--border-default)" }}
        >
          <Search size={32} style={{ color: "var(--text-muted)" }} />
          <p className="text-sm text-center leading-relaxed" style={{ color: "var(--text-muted)" }}>
            읽고 싶은 책의 제목이나<br />저자 이름을 검색해보세요
          </p>
        </div>
      )}

      {/* 서재 추가 모달 */}
      {modalBook && (
        <AddToLibraryModal
          book={modalBook}
          onClose={() => setModalBook(null)}
          onSuccess={handleAddSuccess}
        />
      )}
    </div>
  );
}
