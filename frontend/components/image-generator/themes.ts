/** 이미지 카드 테마 및 폰트 정의 */

export type AspectRatio = "1:1" | "4:5";

export type FontId = "pretendard" | "nanum-gothic" | "ridi-batang";

export interface FontOption {
  id: FontId;
  name: string;
  fontFamily: string;
}

export const FONT_OPTIONS: FontOption[] = [
  {
    id: "pretendard",
    name: "프리텐다드",
    fontFamily: "'Pretendard', 'Apple SD Gothic Neo', sans-serif",
  },
  {
    id: "nanum-gothic",
    name: "나눔고딕",
    fontFamily: "'Nanum Gothic', 'Apple SD Gothic Neo', sans-serif",
  },
  {
    id: "ridi-batang",
    name: "리디바탕",
    fontFamily: "'RIDIBatang', 'Noto Serif KR', Georgia, serif",
  },
];

export interface Theme {
  id: string;
  name: string;
  /** CSS background value (gradient, solid color 등) */
  background: string;
  textColor: string;
  accentColor: string;
  /** 구분선 색상 */
  separatorColor: string;
  fontStyle: "serif" | "sans-serif";
}

// ── 포스트잇 색상 ──────────────────────────────────────────────────────────────

export interface PostitColor {
  id: string;
  name: string;
  /** 포스트잇 카드 배경색 */
  bg: string;
  /** 본문 텍스트 색상 */
  textColor: string;
  /** 출처·보조 텍스트 색상 */
  accentColor: string;
}

export const POSTIT_COLORS: PostitColor[] = [
  { id: "mint",     name: "민트",   bg: "#B8EAE2", textColor: "#1C3A36", accentColor: "#3a7a70" },
  { id: "yellow",   name: "노랑",   bg: "#FEF08A", textColor: "#422006", accentColor: "#854d0e" },
  { id: "pink",     name: "핑크",   bg: "#FBCFE8", textColor: "#4a1028", accentColor: "#9d174d" },
  { id: "blue",     name: "블루",   bg: "#BAE6FD", textColor: "#0c2d3d", accentColor: "#075985" },
  { id: "lavender", name: "라벤더", bg: "#DDD6FE", textColor: "#2e1065", accentColor: "#6d28d9" },
  { id: "peach",    name: "피치",   bg: "#FED7AA", textColor: "#431407", accentColor: "#9a3412" },
];

/** 표지 카드 테마 (6가지) */
export const COVER_THEMES: Theme[] = [
  {
    id: "cinematic",
    name: "시네마틱",
    background: "linear-gradient(160deg, #1a1a1a 0%, #2d2d2d 50%, #111111 100%)",
    textColor: "#f0f0f0",
    accentColor: "#a8a8a8",
    separatorColor: "rgba(255,255,255,0.15)",
    fontStyle: "serif",
  },
  {
    id: "dreaming",
    name: "드리밍",
    background: "linear-gradient(180deg, #c9e8f4 0%, #b8d8ee 40%, #d4e8f5 70%, #e8f4f8 100%)",
    textColor: "#1e3a4a",
    accentColor: "#4a7a98",
    separatorColor: "rgba(30,58,74,0.2)",
    fontStyle: "sans-serif",
  },
  {
    id: "concrete",
    name: "콘크리트",
    background: "linear-gradient(135deg, #8e8e8e 0%, #9e9e9e 30%, #787878 60%, #8a8a8a 100%)",
    textColor: "#f5f5f5",
    accentColor: "#d8d8d8",
    separatorColor: "rgba(255,255,255,0.25)",
    fontStyle: "sans-serif",
  },
  {
    id: "minimal",
    name: "미니멀",
    background: "#FAF7F2",
    textColor: "#1C1917",
    accentColor: "#78716C",
    separatorColor: "#E0D8D0",
    fontStyle: "serif",
  },
  {
    id: "dark-elegance",
    name: "다크 엘레강스",
    background: "linear-gradient(160deg, #140428 0%, #221040 50%, #0e0220 100%)",
    textColor: "#e8d5f8",
    accentColor: "#b890e0",
    separatorColor: "rgba(232,213,248,0.18)",
    fontStyle: "serif",
  },
  {
    id: "forest",
    name: "포레스트",
    background: "linear-gradient(160deg, #0f2310 0%, #1e3a20 50%, #112818 100%)",
    textColor: "#dff0df",
    accentColor: "#88c888",
    separatorColor: "rgba(223,240,223,0.18)",
    fontStyle: "sans-serif",
  },
];

/** 하이라이트 카드 테마 (5가지) */
export const HIGHLIGHT_THEMES: Theme[] = [
  {
    id: "postit",
    name: "포스트잇",
    background: "#B8EAE2",
    textColor: "#1C3A36",
    accentColor: "#3a7a70",
    separatorColor: "transparent",
    fontStyle: "sans-serif",
  },
  {
    id: "dark",
    name: "다크",
    background: "linear-gradient(160deg, #0d0d0d 0%, #1a1a1a 100%)",
    textColor: "#f0f0f0",
    accentColor: "#a0a0a0",
    separatorColor: "rgba(255,255,255,0.12)",
    fontStyle: "serif",
  },
  {
    id: "night-city",
    name: "야경",
    background: "linear-gradient(180deg, #080818 0%, #101028 50%, #080820 100%)",
    textColor: "#e0e0f8",
    accentColor: "#9090d0",
    separatorColor: "rgba(224,224,248,0.15)",
    fontStyle: "serif",
  },
  {
    id: "light-minimal",
    name: "라이트 미니멀",
    background: "#FFFFFF",
    textColor: "#1C1917",
    accentColor: "#78716C",
    separatorColor: "#E5E7EB",
    fontStyle: "serif",
  },
  {
    id: "vintage-paper",
    name: "빈티지 페이퍼",
    background: "linear-gradient(135deg, #F5E8BE 0%, #EDD898 50%, #F0E0A8 100%)",
    textColor: "#3a2a0e",
    accentColor: "#7a5a28",
    separatorColor: "rgba(58,42,14,0.2)",
    fontStyle: "serif",
  },
];
