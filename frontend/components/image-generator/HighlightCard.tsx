"use client";

import React from "react";
import type { Theme, AspectRatio, PostitColor } from "./themes";
import type { UserBook } from "@/lib/types";

interface HighlightCardProps {
  userBook: UserBook;
  theme: Theme;
  aspectRatio: AspectRatio;
  highlightText: string;
  accountName: string;
  bookTitle: string;
  fontFamily: string;
  postitColor: PostitColor;
  customBackground?: string;
  cardRef?: React.RefObject<HTMLDivElement | null>;
}

/**
 * 북스타그램 하이라이트 카드 컴포넌트.
 * artofhaeng 스타일 — 배경 + 인용 텍스트 + 출처 + 계정명.
 * 포스트잇 테마: 커스텀 배경(업로드/AI) 위에 포스트잇 카드 오버레이.
 */
export default function HighlightCard({
  userBook,
  theme,
  aspectRatio,
  highlightText,
  accountName,
  bookTitle,
  fontFamily,
  postitColor,
  customBackground,
  cardRef,
}: HighlightCardProps) {
  const { book } = userBook;
  const isSquare = aspectRatio === "1:1";

  const W = 300;
  const H = isSquare ? 300 : 375;

  const isPostit = theme.id === "postit";
  // 커스텀 배경 여부 (업로드/AI)
  const hasCustomBg = !!customBackground;
  const bg = customBackground || theme.background;
  const isImageBg = bg.startsWith("data:") || bg.startsWith("http") || bg.startsWith("/");

  const textColor = isImageBg && !isPostit ? "#ffffff" : theme.textColor;
  const subColor = isImageBg && !isPostit ? "rgba(255,255,255,0.65)" : theme.accentColor;

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
        justifyContent: "center",
        overflow: "hidden",
        fontFamily,
        flexShrink: 0,
      }}
    >
      {/* ── 배경 레이어 ── */}
      {isImageBg ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={bg}
          alt=""
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }}
          crossOrigin="anonymous"
        />
      ) : isPostit && !hasCustomBg ? (
        /* 포스트잇 기본 배경: 베이지 벽 질감 */
        <div style={{ position: "absolute", inset: 0, background: "#F0EDE8" }} />
      ) : (
        <div style={{ position: "absolute", inset: 0, background: bg }} />
      )}

      {/* 이미지 배경 오버레이 (일반 테마 또는 포스트잇+커스텀배경) */}
      {isImageBg && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: isPostit ? "rgba(0,0,0,0.35)" : "rgba(0,0,0,0.48)",
            pointerEvents: "none",
          }}
        />
      )}

      {/* ── 포스트잇 스타일 ── */}
      {isPostit ? (
        <>
          {/* 마스킹 테이프 */}
          <div
            style={{
              position: "absolute",
              top: "10%",
              left: "18%",
              width: "64px",
              height: "14px",
              background: "rgba(200,190,175,0.7)",
              borderRadius: "2px",
              transform: "rotate(-3deg)",
              zIndex: 1,
            }}
          />
          <div
            style={{
              position: "absolute",
              top: "10%",
              right: "18%",
              width: "64px",
              height: "14px",
              background: "rgba(200,190,175,0.7)",
              borderRadius: "2px",
              transform: "rotate(2deg)",
              zIndex: 1,
            }}
          />

          {/* 포스트잇 본체 */}
          <div
            style={{
              position: "relative",
              zIndex: 2,
              width: "76%",
              background: postitColor.bg,
              borderRadius: "3px",
              padding: "24px 20px 20px",
              boxShadow: "2px 4px 16px rgba(0,0,0,0.18)",
              display: "flex",
              flexDirection: "column",
              gap: "12px",
            }}
          >
            <p
              style={{
                color: postitColor.textColor,
                fontSize: "11px",
                lineHeight: 1.8,
                whiteSpace: "pre-wrap",
              }}
            >
              {highlightText || "이곳에 인상 깊은 문장이 들어갑니다"}
            </p>
            <p
              style={{
                color: postitColor.accentColor,
                fontSize: "10px",
                textAlign: "right",
              }}
            >
              {book.author}, 『{bookTitle}』
            </p>
          </div>
        </>
      ) : (
        /* ── 일반 스타일 ── */
        <div
          style={{
            position: "relative",
            zIndex: 1,
            width: "100%",
            padding: "0 28px",
            display: "flex",
            flexDirection: "column",
            gap: "14px",
          }}
        >
          <p
            style={{
              color: textColor,
              fontSize: "40px",
              lineHeight: 1,
              opacity: 0.35,
              fontFamily: "Georgia, serif",
              marginBottom: "-8px",
            }}
          >
            "
          </p>
          <p
            style={{
              color: textColor,
              fontSize: "12px",
              lineHeight: 1.85,
              whiteSpace: "pre-wrap",
            }}
          >
            {highlightText || (
              <span style={{ opacity: 0.4, fontStyle: "italic" }}>
                이곳에 인상 깊은 문장이 들어갑니다
              </span>
            )}
          </p>
          <p style={{ color: subColor, fontSize: "10px" }}>
            {book.author}, 『{bookTitle}』
          </p>
        </div>
      )}

      {/* 계정명 — 공통 최하단 */}
      <p
        style={{
          position: "absolute",
          bottom: "12px",
          right: "16px",
          color: isPostit
            ? `${postitColor.accentColor}99`
            : subColor,
          fontSize: "9px",
          letterSpacing: "0.07em",
          zIndex: 3,
        }}
      >
        {accountName}
      </p>
    </div>
  );
}
