"use client";

import { useState } from "react";
import Image from "next/image";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { X, BookOpen, Trash2, Save, Highlighter, Plus, Camera } from "lucide-react";
import type { UserBook } from "@/lib/types";
import { updateUserBook, deleteUserBook, addHighlight } from "@/lib/api";
import StarRating from "@/components/ui/StarRating";
import LoadingSpinner from "@/components/ui/LoadingSpinner";

interface Props {
  userBook: UserBook;
  onClose: () => void;
}

interface HighlightEntry {
  content: string;
  note: string;
  page: string;
}

const STATUS_LABELS = [
  { value: "read", label: "읽은 책" },
  { value: "reading", label: "읽고 있는 책" },
  { value: "wishlist", label: "읽고 싶은 책" },
] as const;

/** 책 상세 + 편집 모달 */
export default function BookDetailModal({ userBook, onClose }: Props) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState(userBook.status);
  const [rating, setRating] = useState(userBook.rating ?? 0);
  const [memo, setMemo] = useState(userBook.memo ?? "");
  const [highlights, setHighlights] = useState<HighlightEntry[]>([]);
  const [isDirty, setIsDirty] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  const updateMutation = useMutation({
    mutationFn: async () => {
      await updateUserBook(userBook.id, {
        status,
        rating: rating || null,
        memo: memo || null,
      });
      const validHighlights = highlights.filter((h) => h.content.trim());
      await Promise.all(
        validHighlights.map((h) =>
          addHighlight({
            user_book_id: userBook.id,
            content: h.content.trim(),
            note: h.note.trim() || undefined,
            page: h.page ? parseInt(h.page, 10) : undefined,
          })
        )
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["myBooks"] });
      queryClient.invalidateQueries({ queryKey: ["myStats"] });
      setIsDirty(false);
      setHighlights([]);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteUserBook(userBook.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["myBooks"] });
      queryClient.invalidateQueries({ queryKey: ["myStats"] });
      onClose();
    },
  });

  const handleStatusChange = (v: typeof status) => {
    setStatus(v);
    if (v !== "read") {
      setRating(0);
    }
    setIsDirty(true);
  };
  const handleRatingChange = (v: number) => { setRating(v); setIsDirty(true); };
  const handleMemoChange = (v: string) => { setMemo(v); setIsDirty(true); };

  const addHighlightEntry = () => {
    setHighlights((prev) => [...prev, { content: "", note: "", page: "" }]);
    setIsDirty(true);
  };

  const removeHighlightEntry = (index: number) => {
    setHighlights((prev) => prev.filter((_, i) => i !== index));
  };

  const updateHighlightEntry = (index: number, field: keyof HighlightEntry, value: string) => {
    setHighlights((prev) =>
      prev.map((h, i) => (i === index ? { ...h, [field]: value } : h))
    );
    setIsDirty(true);
  };

  const { book } = userBook;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4"
      style={{ background: "rgba(28, 25, 23, 0.5)", backdropFilter: "blur(4px)" }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="w-full max-w-lg rounded-3xl overflow-hidden animate-fade-in"
        style={{
          background: "var(--bg-card)",
          boxShadow: "var(--shadow-lg)",
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* 모달 헤더 */}
        <div
          className="flex items-center justify-between px-5 py-4"
          style={{ borderBottom: "1px solid var(--border-default)" }}
        >
          <h2 className="text-base font-bold" style={{ color: "var(--text-primary)" }}>
            책 상세
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-xl transition-colors cursor-pointer"
            style={{ color: "var(--text-muted)" }}
            aria-label="닫기"
          >
            <X size={20} />
          </button>
        </div>

        {/* 스크롤 영역 */}
        <div className="overflow-y-auto flex-1">
          {/* 책 기본 정보 */}
          <div className="p-5 flex gap-4">
            <div
              className="flex-shrink-0 rounded-2xl overflow-hidden"
              style={{
                width: "80px",
                height: "110px",
                background: "var(--bg-subtle)",
                border: "1px solid var(--border-default)",
              }}
            >
              {book.cover_image_url ? (
                <Image
                  src={book.cover_image_url}
                  alt={book.title}
                  width={80}
                  height={110}
                  className="w-full h-full object-cover"
                  unoptimized
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <BookOpen size={24} style={{ color: "var(--text-muted)" }} />
                </div>
              )}
            </div>
            <div className="flex flex-col gap-1.5 flex-1 min-w-0">
              <h3
                className="text-base font-bold leading-snug"
                style={{ color: "var(--text-primary)" }}
              >
                {book.title}
              </h3>
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                {book.author}
              </p>
              <div className="flex flex-wrap gap-1.5 items-center">
                {book.publisher && (
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    {book.publisher}
                  </span>
                )}
                {book.publisher && book.published_at && (
                  <span className="text-xs" style={{ color: "var(--border-default)" }}>·</span>
                )}
                {book.published_at && (
                  <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                    {book.published_at.slice(0, 7)}
                  </span>
                )}
              </div>
              {book.genre && (
                <span
                  className="badge w-fit"
                  style={{ background: "var(--accent-light)", color: "var(--accent-dark)" }}
                >
                  {book.genre}
                </span>
              )}
            </div>
          </div>

          {/* 책 설명 */}
          {book.description && (
            <div
              className="mx-5 mb-4 p-4 rounded-2xl"
              style={{ background: "var(--bg-subtle)" }}
            >
              <p
                className="text-xs leading-relaxed line-clamp-3"
                style={{ color: "var(--text-secondary)" }}
              >
                {book.description}
              </p>
            </div>
          )}

          {/* 독서 상태 */}
          <div className="px-5 mb-4">
            <p className="text-xs font-semibold mb-2" style={{ color: "var(--text-muted)" }}>
              독서 상태
            </p>
            <div className="flex gap-2 flex-wrap">
              {STATUS_LABELS.map(({ value, label }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => handleStatusChange(value)}
                  className="px-4 py-2 rounded-xl text-sm font-medium transition-all cursor-pointer"
                  style={{
                    background: status === value ? "var(--accent)" : "var(--bg-subtle)",
                    color: status === value ? "white" : "var(--text-secondary)",
                    border: "1px solid",
                    borderColor: status === value ? "var(--accent)" : "var(--border-default)",
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* 별점 — 읽은 책일 때만 표시 */}
          {status === "read" && (
            <div className="px-5 mb-4">
              <p className="text-xs font-semibold mb-2" style={{ color: "var(--text-muted)" }}>
                별점
              </p>
              <StarRating value={rating} onChange={handleRatingChange} size={24} />
            </div>
          )}

          {/* 독서 메모 */}
          <div className="px-5 mb-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
                독서 메모
              </p>
              <button
                type="button"
                onClick={() => alert("현재 준비중인 서비스입니다.")}
                className="flex items-center gap-1 text-[11px] font-medium px-2.5 py-1.5 rounded-xl transition-colors cursor-pointer"
                style={{
                  color: "var(--accent-dark)",
                  background: "var(--accent-light)",
                  border: "1px solid #FDE68A",
                }}
              >
                <Camera size={11} />
                북스타그램 이미지 생성
              </button>
            </div>
            <textarea
              value={memo}
              onChange={(e) => handleMemoChange(e.target.value)}
              placeholder="이 책에 대한 생각을 적어보세요..."
              rows={3}
              className="w-full px-3.5 py-3 text-sm rounded-2xl resize-none"
              style={{
                background: "var(--bg-subtle)",
                border: "1px solid var(--border-default)",
                color: "var(--text-primary)",
                outline: "none",
              }}
              onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
              onBlur={(e) => (e.target.style.borderColor = "var(--border-default)")}
            />
          </div>

          {/* 하이라이트 */}
          <div className="px-5 mb-5">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
                하이라이트 <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>(선택)</span>
              </p>
              <button
                type="button"
                onClick={addHighlightEntry}
                className="flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-xl transition-colors cursor-pointer"
                style={{
                  color: "var(--accent-dark)",
                  background: "var(--accent-light)",
                  border: "1px solid #FDE68A",
                }}
              >
                <Plus size={12} />
                추가
              </button>
            </div>

            {highlights.length === 0 ? (
              <button
                type="button"
                onClick={addHighlightEntry}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl text-xs transition-colors cursor-pointer"
                style={{
                  border: "1.5px dashed var(--border-default)",
                  color: "var(--text-muted)",
                }}
              >
                <Highlighter size={14} />
                기억하고 싶은 문장 추가하기
              </button>
            ) : (
              <div className="flex flex-col gap-3">
                {highlights.map((h, idx) => (
                  <div
                    key={idx}
                    className="rounded-2xl p-3 flex flex-col gap-2"
                    style={{ background: "var(--bg-subtle)", border: "1px solid var(--border-default)" }}
                  >
                    <div className="flex items-start gap-2">
                      <textarea
                        value={h.content}
                        onChange={(e) => updateHighlightEntry(idx, "content", e.target.value)}
                        placeholder="하이라이트할 문장을 입력하세요"
                        rows={2}
                        className="flex-1 px-3 py-2 text-xs rounded-xl resize-none"
                        style={{
                          background: "var(--bg-card)",
                          border: "1px solid var(--border-default)",
                          color: "var(--text-primary)",
                          outline: "none",
                        }}
                        onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
                        onBlur={(e) => (e.target.style.borderColor = "var(--border-default)")}
                      />
                      <button
                        type="button"
                        onClick={() => removeHighlightEntry(idx)}
                        className="p-1.5 rounded-xl transition-colors cursor-pointer flex-shrink-0 mt-0.5"
                        style={{ color: "var(--text-muted)" }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={h.note}
                        onChange={(e) => updateHighlightEntry(idx, "note", e.target.value)}
                        placeholder="메모 (선택)"
                        className="flex-1 px-3 py-1.5 text-xs rounded-xl"
                        style={{
                          background: "var(--bg-card)",
                          border: "1px solid var(--border-default)",
                          color: "var(--text-primary)",
                          outline: "none",
                        }}
                        onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
                        onBlur={(e) => (e.target.style.borderColor = "var(--border-default)")}
                      />
                      <input
                        type="number"
                        value={h.page}
                        onChange={(e) => updateHighlightEntry(idx, "page", e.target.value)}
                        placeholder="페이지"
                        min={1}
                        className="w-20 px-3 py-1.5 text-xs rounded-xl"
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
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 액션 버튼 */}
        <div
          className="flex items-center justify-between gap-3 px-5 py-4"
          style={{ borderTop: "1px solid var(--border-default)" }}
        >
          {/* 삭제 */}
          {deleteConfirm ? (
            <div className="flex items-center gap-2">
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                정말 삭제할까요?
              </span>
              <button
                type="button"
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                style={{ background: "#EF4444", color: "white", border: "none" }}
              >
                {deleteMutation.isPending ? <LoadingSpinner size={12} /> : <Trash2 size={12} />}
                삭제
              </button>
              <button
                type="button"
                onClick={() => setDeleteConfirm(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer"
                style={{ background: "var(--bg-subtle)", color: "var(--text-muted)", border: "1px solid var(--border-default)" }}
              >
                취소
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setDeleteConfirm(true)}
              disabled={deleteMutation.isPending}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm transition-colors cursor-pointer"
              style={{ color: "#EF4444", background: "#FEF2F2" }}
            >
              <Trash2 size={14} />
              삭제
            </button>
          )}

          {/* 저장 */}
          <button
            type="button"
            onClick={() => updateMutation.mutate()}
            disabled={!isDirty || updateMutation.isPending}
            className="btn-primary"
            style={{ opacity: !isDirty ? 0.5 : 1, cursor: !isDirty ? "not-allowed" : "pointer" }}
          >
            {updateMutation.isPending ? <LoadingSpinner size={14} /> : <Save size={14} />}
            저장
          </button>
        </div>
      </div>
    </div>
  );
}
