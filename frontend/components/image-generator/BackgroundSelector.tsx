"use client";

import { useRef } from "react";
import { Upload, Sparkles, Loader2, RefreshCw } from "lucide-react";
import ThemeSelector from "./ThemeSelector";
import type { Theme } from "./themes";

export type BgTab = "theme" | "upload" | "ai";

interface BackgroundSelectorProps {
  themes: Theme[];
  activeTab: BgTab;
  onTabChange: (tab: BgTab) => void;
  selectedThemeId: string;
  onThemeSelect: (theme: Theme) => void;
  uploadedBg: string | null;
  onUpload: (dataUrl: string) => void;
  onClearUpload: () => void;
  // AI 생성 관련
  aiImageUrl: string | null;
  aiRemaining: number;
  aiLimit: number;
  isGenerating: boolean;
  aiError: string | null;
  onGenerateAi: () => void;
  onClearAi: () => void;
}

/** 배경 선택기 — 무드 테마 / 직접 업로드 / AI 생성 탭 */
export default function BackgroundSelector({
  themes,
  activeTab,
  onTabChange,
  selectedThemeId,
  onThemeSelect,
  uploadedBg,
  onUpload,
  onClearUpload,
  aiImageUrl,
  aiRemaining,
  aiLimit,
  isGenerating,
  aiError,
  onGenerateAi,
  onClearAi,
}: BackgroundSelectorProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      alert("이미지 파일만 업로드할 수 있어요.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      alert("10MB 이하의 이미지만 업로드할 수 있어요.");
      return;
    }
    const reader = new FileReader();
    reader.onload = (ev) => {
      if (ev.target?.result) onUpload(ev.target.result as string);
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  const TAB_STYLES = (active: boolean) => ({
    padding: "6px 10px",
    borderRadius: "10px",
    fontSize: "11px",
    fontWeight: active ? 600 : 400,
    cursor: "pointer",
    border: "none",
    background: active ? "var(--accent)" : "transparent",
    color: active ? "white" : "var(--text-muted)",
    transition: "all 0.15s",
    display: "flex",
    alignItems: "center",
    gap: "4px",
  });

  return (
    <div className="flex flex-col gap-3">
      {/* 탭 */}
      <div
        className="flex gap-1 p-1 rounded-xl"
        style={{ background: "var(--bg-subtle)" }}
      >
        <button type="button" style={TAB_STYLES(activeTab === "theme")} onClick={() => onTabChange("theme")}>
          무드 테마
        </button>
        <button type="button" style={TAB_STYLES(activeTab === "upload")} onClick={() => onTabChange("upload")}>
          업로드
        </button>
        <button type="button" style={TAB_STYLES(activeTab === "ai")} onClick={() => onTabChange("ai")}>
          <Sparkles size={11} />
          AI 생성
        </button>
      </div>

      {/* 무드 테마 탭 */}
      {activeTab === "theme" && (
        <ThemeSelector themes={themes} selectedId={selectedThemeId} onSelect={onThemeSelect} />
      )}

      {/* 업로드 탭 */}
      {activeTab === "upload" && (
        <div className="flex flex-col gap-3">
          {uploadedBg ? (
            <div className="relative rounded-xl overflow-hidden" style={{ aspectRatio: "3/2" }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={uploadedBg}
                alt="업로드된 배경"
                style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
              />
              <button
                type="button"
                onClick={onClearUpload}
                className="absolute top-2 right-2 px-2.5 py-1 rounded-lg text-xs font-medium cursor-pointer"
                style={{ background: "rgba(0,0,0,0.55)", color: "white" }}
              >
                제거
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex flex-col items-center justify-center gap-2 rounded-xl cursor-pointer transition-all"
              style={{
                aspectRatio: "3/2",
                border: "2px dashed var(--border-default)",
                background: "var(--bg-subtle)",
                color: "var(--text-muted)",
              }}
            >
              <Upload size={20} />
              <span className="text-xs">이미지 업로드</span>
              <span className="text-[10px]" style={{ color: "var(--text-muted)", opacity: 0.7 }}>
                JPG, PNG, WEBP · 최대 10MB
              </span>
            </button>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={handleFileChange}
          />
        </div>
      )}

      {/* AI 생성 탭 */}
      {activeTab === "ai" && (
        <div className="flex flex-col gap-3">
          {/* 남은 횟수 배지 */}
          <div className="flex items-center justify-between">
            <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>
              책 분위기에 맞는 배경을 AI가 만들어드려요
            </p>
            <span
              className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
              style={{
                background: aiRemaining > 0 ? "var(--accent-light)" : "var(--bg-subtle)",
                color: aiRemaining > 0 ? "var(--accent-dark)" : "var(--text-muted)",
              }}
            >
              오늘 {aiRemaining}/{aiLimit}
            </span>
          </div>

          {/* 생성된 이미지 미리보기 */}
          {aiImageUrl ? (
            <div className="relative rounded-xl overflow-hidden" style={{ aspectRatio: "1/1" }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={aiImageUrl}
                alt="AI 생성 배경"
                style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
              />
              <div className="absolute bottom-0 left-0 right-0 flex gap-1.5 p-2">
                {aiRemaining > 0 && (
                  <button
                    type="button"
                    onClick={onGenerateAi}
                    disabled={isGenerating}
                    className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-medium cursor-pointer"
                    style={{ background: "rgba(0,0,0,0.6)", color: "white" }}
                  >
                    {isGenerating ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
                    재생성
                  </button>
                )}
                <button
                  type="button"
                  onClick={onClearAi}
                  className="flex-1 py-1.5 rounded-lg text-xs font-medium cursor-pointer"
                  style={{ background: "rgba(0,0,0,0.6)", color: "white" }}
                >
                  제거
                </button>
              </div>
            </div>
          ) : (
            /* 생성 버튼 */
            <button
              type="button"
              onClick={onGenerateAi}
              disabled={isGenerating || aiRemaining === 0}
              className="flex flex-col items-center justify-center gap-2 rounded-xl transition-all"
              style={{
                aspectRatio: "3/2",
                border: `2px dashed ${aiRemaining === 0 ? "var(--border-default)" : "var(--accent)"}`,
                background: aiRemaining === 0 ? "var(--bg-subtle)" : "var(--accent-light)",
                color: aiRemaining === 0 ? "var(--text-muted)" : "var(--accent-dark)",
                cursor: aiRemaining === 0 ? "not-allowed" : "pointer",
                opacity: isGenerating ? 0.7 : 1,
              }}
            >
              {isGenerating ? (
                <>
                  <Loader2 size={22} className="animate-spin" />
                  <span className="text-xs font-medium">AI가 이미지를 만들고 있어요...</span>
                  <span className="text-[10px]" style={{ opacity: 0.7 }}>약 10~20초 소요</span>
                </>
              ) : aiRemaining === 0 ? (
                <>
                  <Sparkles size={22} />
                  <span className="text-xs">오늘 횟수를 모두 사용했어요</span>
                  <span className="text-[10px]" style={{ opacity: 0.7 }}>내일 다시 시도해주세요</span>
                </>
              ) : (
                <>
                  <Sparkles size={22} />
                  <span className="text-xs font-medium">AI 배경 생성하기</span>
                  <span className="text-[10px]" style={{ opacity: 0.7 }}>책 분위기에 맞게 자동 생성</span>
                </>
              )}
            </button>
          )}

          {/* 에러 메시지 */}
          {aiError && (
            <p className="text-xs" style={{ color: "#EF4444" }}>
              {aiError}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
