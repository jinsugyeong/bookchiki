"use client";

import Image from "next/image";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, ThumbsDown, Heart, Check } from "lucide-react";
import type { Recommendation, UserBook } from "@/lib/types";
import { selectAladinBook, addToLibrary, getMyBooks } from "@/lib/api";
import LoadingSpinner from "@/components/ui/LoadingSpinner";

interface RecommendCardProps {
  recommendation: Recommendation;
  onDislike?: () => void;
  isRefreshing?: boolean;
}

/** 추천 책 카드 */
export default function RecommendCard({
  recommendation,
  onDislike,
  isRefreshing = false,
}: RecommendCardProps) {
  const queryClient = useQueryClient();
  const { title, author, description, cover_image_url, genre, reason, score } = recommendation;

  // 이미 서재에 추가된 책인지 확인 (캐시 우선)
  const { data: myBooks } = useQuery<UserBook[]>({
    queryKey: ["myBooks"],
    queryFn: () => getMyBooks({ limit: 500 }),
    staleTime: 60_000,
  });

  const isAlreadyAdded = (myBooks ?? []).some(
    (ub) =>
      ub.book.title === title && ub.book.author === author
  );

  /** 내 서재에 추가 (wishlist) */
  const addMutation = useMutation({
    mutationFn: async () => {
      const book = await selectAladinBook({
        title,
        author,
        cover_image_url,
        genre,
        description,
      });
      await addToLibrary({ book_id: book.id, status: "wishlist" });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["myBooks"] });
      queryClient.invalidateQueries({ queryKey: ["myStats"] });
    },
  });

  const added = isAlreadyAdded || addMutation.isSuccess;

  return (
    <div
      className="card flex flex-col gap-3 animate-fade-in overflow-hidden"
      style={{
        opacity: isRefreshing ? 0.5 : 1,
        transition: "opacity 0.2s ease",
      }}
    >
      {/* 표지 + 정보 */}
      <div className="p-4 flex gap-3">
        {/* 표지 */}
        <div
          className="flex-shrink-0 rounded-xl overflow-hidden"
          style={{
            width: "72px",
            height: "100px",
            background: "var(--bg-subtle)",
            border: "1px solid var(--border-default)",
          }}
        >
          {cover_image_url ? (
            <Image
              src={cover_image_url}
              alt={title}
              width={72}
              height={100}
              className="w-full h-full object-cover"
              unoptimized
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <BookOpen size={22} style={{ color: "var(--text-muted)" }} />
            </div>
          )}
        </div>

        {/* 텍스트 */}
        <div className="flex-1 min-w-0 flex flex-col gap-1">
          <h3
            className="text-sm font-bold leading-snug line-clamp-2"
            style={{ color: "var(--text-primary)" }}
          >
            {title}
          </h3>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            {author}
          </p>
          {genre && (
            <span
              className="badge w-fit text-[11px]"
              style={{ background: "var(--accent-light)", color: "var(--accent-dark)" }}
            >
              {genre}
            </span>
          )}
        </div>
      </div>

      {/* 매칭 점수 바 */}
      <div className="px-4 flex items-center gap-2">
        <div
          className="flex-1 rounded-full overflow-hidden"
          style={{ height: "6px", background: "var(--bg-subtle)" }}
        >
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${Math.min(Math.round(score * 100), 100)}%`,
              background: "var(--accent)",
            }}
          />
        </div>
        <span className="text-[11px] flex-shrink-0 tabular-nums" style={{ color: "var(--text-muted)" }}>
          {Math.min(Math.round(score * 100), 100)}% 매칭
        </span>
      </div>

      {/* 추천 이유 */}
      {reason && (
        <div
          className="mx-4 rounded-xl p-3"
          style={{ background: "var(--accent-light)", border: "1px solid #FDE68A" }}
        >
          <p className="text-xs leading-relaxed" style={{ color: "#92400E" }}>
            {reason}
          </p>
        </div>
      )}

      {/* 책 설명 */}
      {description && (
        <p
          className="px-4 text-xs leading-relaxed"
          style={{ color: "var(--text-secondary)" }}
        >
          {description}
        </p>
      )}

      {/* 액션 버튼 */}
      <div
        className="px-4 pb-4 flex items-center gap-2 mt-auto"
      >
        {/* 마음에 안들어요 */}
        {onDislike && (
          <button
            type="button"
            onClick={onDislike}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-colors cursor-pointer"
            style={{
              color: "var(--text-muted)",
              background: "var(--bg-subtle)",
              border: "1px solid var(--border-default)",
            }}
          >
            <ThumbsDown size={13} />
            다른 책
          </button>
        )}

        {/* 서재에 추가 */}
        <button
          type="button"
          onClick={() => !added && !addMutation.isPending && addMutation.mutate()}
          disabled={added || addMutation.isPending}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold ml-auto transition-all cursor-pointer"
          style={{
            background: added ? "var(--status-read-bg)" : "var(--accent)",
            color: added ? "var(--status-read)" : "white",
            border: "none",
            opacity: addMutation.isPending ? 0.7 : 1,
          }}
        >
          {addMutation.isPending ? (
            <LoadingSpinner size={12} />
          ) : added ? (
            <Check size={13} />
          ) : (
            <Heart size={13} />
          )}
          {added ? "서재에 추가됨" : "읽고 싶어요"}
        </button>
      </div>
    </div>
  );
}
