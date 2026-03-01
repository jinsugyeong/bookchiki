"use client";

import Image from "next/image";
import { BookOpen } from "lucide-react";
import type { UserBook } from "@/lib/types";
import StarRating from "@/components/ui/StarRating";
import StatusBadge from "@/components/ui/StatusBadge";

interface BookCardProps {
  userBook: UserBook;
  onClick?: () => void;
}

/** 내 서재 책 카드 */
export default function BookCard({ userBook, onClick }: BookCardProps) {
  const { book, status, rating, memo } = userBook;

  return (
    <button
      type="button"
      onClick={onClick}
      className="card text-left w-full flex gap-3 p-3.5 cursor-pointer group hover:shadow-md"
      style={{ transition: "box-shadow 0.2s ease, transform 0.15s ease" }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.transform = "translateY(-2px)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
      }}
    >
      {/* 책 표지 */}
      <div
        className="flex-shrink-0 rounded-xl overflow-hidden"
        style={{
          width: "64px",
          height: "88px",
          background: "var(--bg-subtle)",
          border: "1px solid var(--border-default)",
        }}
      >
        {book.cover_image_url ? (
          <Image
            src={book.cover_image_url}
            alt={book.title}
            width={64}
            height={88}
            className="w-full h-full object-cover"
            unoptimized
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <BookOpen size={20} style={{ color: "var(--text-muted)" }} />
          </div>
        )}
      </div>

      {/* 책 정보 */}
      <div className="flex flex-col flex-1 min-w-0 gap-1">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p
              className="text-sm font-semibold leading-snug line-clamp-2"
              style={{ color: "var(--text-primary)" }}
            >
              {book.title}
            </p>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
              {book.author}
            </p>
          </div>
          <StatusBadge status={status} />
        </div>

        {/* 별점 */}
        {(rating ?? 0) > 0 && (
          <StarRating value={rating} readonly size={13} />
        )}

        {/* 메모 미리보기 */}
        {memo && (
          <p
            className="text-xs line-clamp-2 mt-0.5"
            style={{ color: "var(--text-secondary)" }}
          >
            {memo}
          </p>
        )}

      </div>
    </button>
  );
}
