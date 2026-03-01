import axios from "axios";
import type {
  Book,
  UserBook,
  AladinBook,
  ReadingStats,
  RecommendationResponse,
  UserProfile,
  ImportResult,
  Highlight,
} from "./types";

/** API 클라이언트 — 개발 환경에서는 JWT 없이도 동작 */
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  headers: {
    "Content-Type": "application/json",
  },
});

/** 로컬 스토리지에서 토큰 읽어서 헤더에 주입 */
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// ── 인증 ─────────────────────────────────────────────────────────────────────

/** 내 정보 조회 */
export const getMe = async () => {
  const { data } = await api.get("/auth/me");
  return data;
};

/** Google OAuth 코드로 JWT 교환 (code는 query param) */
export const loginWithGoogle = async (code: string) => {
  const { data } = await api.post(`/auth/google?code=${encodeURIComponent(code)}`);
  return data;
};

/** 계정 탈퇴 (모든 데이터 삭제) */
export const deleteAccount = async (): Promise<void> => {
  await api.delete("/auth/me");
};

// ── 도서 ──────────────────────────────────────────────────────────────────────

/** 책 단건 조회 */
export const getBook = async (bookId: string): Promise<Book> => {
  const { data } = await api.get(`/books/${bookId}`);
  return data;
};

/** 알라딘 API 책 검색 */
export const searchAladin = async (q: string, maxResults = 20): Promise<AladinBook[]> => {
  const { data } = await api.get("/books/search/aladin", {
    params: { q, max_results: maxResults },
  });
  return data;
};

/** 알라딘 검색 결과 선택해서 books 테이블에 저장 */
export const selectAladinBook = async (book: AladinBook): Promise<Book> => {
  const { data } = await api.post("/books/search/aladin/select", book);
  return data;
};

// ── 내 서재 ──────────────────────────────────────────────────────────────────

/** 내 서재 목록 조회 */
export const getMyBooks = async (params?: {
  status?: string;
  skip?: number;
  limit?: number;
}): Promise<UserBook[]> => {
  const { data } = await api.get("/my-books", { params });
  return data;
};

/** 내 서재 독서 통계 */
export const getMyStats = async (): Promise<ReadingStats> => {
  const { data } = await api.get("/my-books/stats");
  return data;
};

/** 서재에 책 추가 */
export const addToLibrary = async (payload: {
  book_id: string;
  status: string;
  rating?: number | null;
  memo?: string;
}): Promise<UserBook> => {
  const { data } = await api.post("/my-books", payload);
  return data;
};

/** 서재 책 정보 수정 */
export const updateUserBook = async (
  userBookId: string,
  payload: {
    status?: string;
    rating?: number | null;
    memo?: string | null;
    finished_at?: string | null;
  }
): Promise<UserBook> => {
  const { data } = await api.patch(`/my-books/${userBookId}`, payload);
  return data;
};

/** 서재에서 책 삭제 */
export const deleteUserBook = async (userBookId: string): Promise<void> => {
  await api.delete(`/my-books/${userBookId}`);
};

// ── 하이라이트 ───────────────────────────────────────────────────────────────

/** 하이라이트 목록 조회 */
export const getHighlights = async (userBookId: string): Promise<Highlight[]> => {
  const { data } = await api.get(`/highlights`, { params: { user_book_id: userBookId } });
  return data;
};

/** 하이라이트 추가 */
export const addHighlight = async (payload: {
  user_book_id: string;
  content: string;
  note?: string;
  page?: number;
}): Promise<Highlight> => {
  const { data } = await api.post("/highlights", payload);
  return data;
};

/** 하이라이트 수정 */
export const updateHighlight = async (
  highlightId: string,
  payload: { content?: string; note?: string; page?: number }
): Promise<Highlight> => {
  const { data } = await api.patch(`/highlights/${highlightId}`, payload);
  return data;
};

/** 하이라이트 삭제 */
export const deleteHighlight = async (highlightId: string): Promise<void> => {
  await api.delete(`/highlights/${highlightId}`);
};

// ── 추천 ──────────────────────────────────────────────────────────────────────

/** 기록 기반 개인화 추천 (시스템 1) */
export const getRecommendations = async (limit = 3): Promise<RecommendationResponse> => {
  const { data } = await api.get("/recommendations", { params: { limit } });
  return data;
};

/** 질문 기반 맞춤 추천 (시스템 2) */
export const askRecommendation = async (question: string): Promise<RecommendationResponse> => {
  const { data } = await api.post("/recommendations/ask", { question });
  // 백엔드가 { results: AskResultItem[] } 형태로 반환하므로 Recommendation[]으로 변환
  if (data.results && !data.recommendations) {
    return {
      recommendations: (data.results as any[]).map((item, idx) => ({
        book_id: item.isbn || `ask-${idx}`,
        title: item.title ?? "",
        author: item.author ?? "",
        description: item.description ?? "",
        genre: item.genre ?? "",
        cover_image_url: item.cover_image_url ?? "",
        score: 0.8,
        reason: item.reason ?? "",
      })),
      total: data.total ?? 0,
    };
  }
  return data;
};

/** 추천 강제 재생성 */
export const refreshRecommendations = async (limit = 3): Promise<RecommendationResponse> => {
  const { data } = await api.post("/recommendations/refresh", null, {
    params: { limit },
  });
  return data;
};

/** 취향 프로필 조회 */
export const getUserProfile = async (): Promise<UserProfile> => {
  const { data } = await api.get("/recommendations/profile");
  return data;
};

// ── CSV 임포트 ─────────────────────────────────────────────────────────────────

/** CSV 파일 임포트 (multipart/form-data) */
export const importCSV = async (file: File): Promise<ImportResult> => {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/imports/csv", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
};

export default api;
