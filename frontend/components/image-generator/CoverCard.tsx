"use client";

import React from "react";
import type { Theme, AspectRatio } from "./themes";
import type { UserBook } from "@/lib/types";

interface CoverCardProps {
  userBook: UserBook;
  theme: Theme;
  aspectRatio: AspectRatio;
  reviewText: string;
  accountName: string;
  bookTitle: string;
  fontFamily: string;
  /** 커스텀 배경: CSS value(그라디언트) 또는 data URL(업로드 이미지) */
  customBackground?: string;
  cardRef?: React.RefObject<HTMLDivElement | null>;
}

/**
 * 북스타그램 표지 카드 컴포넌트.
 * artofhaeng 스타일 — 배경 + 책표지 + 제목/저자 + 리뷰텍스트 + 계정명.
 */
export default function CoverCard({
  userBook,
  theme,
  aspectRatio,
  reviewText,
  accountName,
  bookTitle,
  fontFamily,
  customBackground,
  cardRef,
}: CoverCardProps) {
  const { book } = userBook;
  const isSquare = aspectRatio === "1:1";

  // 미리보기 기준 크기 (실제 캡처는 3배 해상도)
  const W = 300;
  const H = isSquare ? 300 : 375;

  const bg = customBackground || theme.background;
  const isImageBg = bg.startsWith("data:") || bg.startsWith("http") || bg.startsWith("/");

  const proxyUrl = book.cover_image_url
    ? `/api/proxy-image?url=${encodeURIComponent(book.cover_image_url)}`
    : null;

  return (
    <div
      ref={cardRef}
      style={{
        width: `${W}px`,
        height: `${H}px`,
        position: "relative",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "flex-end",
        overflow: "hidden",
        fontFamily,
        flexShrink: 0,
      }}
    >
      {/* 배경 */}
      {isImageBg ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={bg}
          alt=""
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
          crossOrigin="anonymous"
        />
      ) : (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: bg,
          }}
        />
      )}

      {/* 오버레이 (텍스트 가독성) */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "linear-gradient(to top, rgba(0,0,0,0.55) 0%, transparent 60%)",
          pointerEvents: "none",
        }}
      />

      {/* 책 표지 — 카드 상단 중앙 */}
      <div
        style={{
          position: "absolute",
          top: "14%",
          left: "50%",
          transform: "translateX(-50%)",
          width: isSquare ? "90px" : "100px",
          height: isSquare ? "128px" : "142px",
          borderRadius: "5px",
          overflow: "hidden",
          boxShadow: "0 6px 20px rgba(0,0,0,0.45)",
          background: "rgba(255,255,255,0.15)",
          flexShrink: 0,
        }}
      >
        {proxyUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={proxyUrl}
            alt={book.title}
            style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
            crossOrigin="anonymous"
          />
        ) : (
          <div
            style={{
              width: "100%",
              height: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "rgba(255,255,255,0.1)",
            }}
          >
            <span style={{ color: "rgba(255,255,255,0.6)", fontSize: "10px" }}>표지 없음</span>
          </div>
        )}
      </div>

      {/* 하단 텍스트 영역 */}
      <div
        style={{
          position: "relative",
          zIndex: 1,
          width: "100%",
          padding: "0 20px 16px",
          display: "flex",
          flexDirection: "column",
          gap: "6px",
        }}
      >
        {/* 구분선 */}
        <div
          style={{
            width: "100%",
            height: "1px",
            background: isImageBg ? "rgba(255,255,255,0.3)" : theme.separatorColor,
            marginBottom: "8px",
          }}
        />

        {/* 책 제목 */}
        <p
          style={{
            color: isImageBg ? "#ffffff" : theme.textColor,
            fontSize: "14px",
            fontWeight: 700,
            lineHeight: 1.35,
            margin: 0,
          }}
        >
          {bookTitle}
        </p>

        {/* 저자 | 출판사 */}
        <p
          style={{
            color: isImageBg ? "rgba(255,255,255,0.75)" : theme.accentColor,
            fontSize: "10px",
            margin: 0,
          }}
        >
          {book.author}
          {book.publisher ? ` | ${book.publisher}` : ""}
        </p>

        {/* 리뷰 텍스트 */}
        {reviewText ? (
          <p
            style={{
              color: isImageBg ? "rgba(255,255,255,0.88)" : theme.textColor,
              fontSize: "10px",
              lineHeight: 1.7,
              opacity: 0.9,
              whiteSpace: "pre-wrap",
              margin: "4px 0 0",
            }}
          >
            {reviewText}
          </p>
        ) : (
          <p
            style={{
              color: isImageBg ? "rgba(255,255,255,0.35)" : `${theme.accentColor}88`,
              fontSize: "10px",
              lineHeight: 1.7,
              fontStyle: "italic",
              margin: "4px 0 0",
            }}
          >
            이곳에 한 줄 리뷰가 들어갑니다
          </p>
        )}

        {/* 계정명 */}
        <p
          style={{
            color: isImageBg ? "rgba(255,255,255,0.5)" : theme.accentColor,
            fontSize: "9px",
            letterSpacing: "0.08em",
            marginTop: "6px",
            textAlign: "right",
          }}
        >
          {accountName}
        </p>
      </div>
    </div>
  );
}
