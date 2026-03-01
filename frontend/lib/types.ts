/** 책 기본 정보 */
export interface Book {
  id: string;
  title: string;
  author: string;
  isbn?: string;
  description?: string;
  cover_image_url?: string;
  genre?: string;
  publisher?: string;
  published_at?: string;
  created_at?: string;
}

/** 내 서재 책 */
export interface UserBook {
  id: string;
  user_id: string;
  book_id: string;
  book: Book;
  status: "read" | "reading" | "wishlist";
  rating?: number | null;
  memo?: string | null;
  source: "manual" | "import";
  created_at: string;
  finished_at?: string | null;
}

/** 알라딘 검색 결과 */
export interface AladinBook {
  title: string;
  author: string;
  isbn?: string;
  description?: string;
  cover_image_url?: string;
  genre?: string;
  publisher?: string;
  published_at?: string;
}

/** 독서 통계 */
export interface ReadingStats {
  total_books: number;
  books_read: number;
  books_reading: number;
  books_wishlist: number;
  average_rating: number;
  genre_distribution: Record<string, number>;
  monthly_counts: Record<string, number>;
}

/** 추천 책 */
export interface Recommendation {
  book_id: string;
  title: string;
  author: string;
  description?: string;
  genre?: string;
  cover_image_url?: string;
  score: number;
  reason?: string;
  mood?: string;
}

/** 추천 응답 */
export interface RecommendationResponse {
  recommendations: Recommendation[];
  total: number;
  cache_status?: string;
  profile_version?: number;
  profile_computed_at?: string;
}

/** 취향 프로필 */
export interface UserProfile {
  profile_data?: {
    preferred_genres?: string[];
    disliked_genres?: string[];
    preference_summary?: string;
    top_rated_books?: Array<{ title: string; author: string; rating: number }>;
    reading_count?: number;
    memo_analyzed_at?: string;
  };
  is_dirty: boolean;
  dirty_reason?: string | null;
  version?: number;
  profile_computed_at?: string;
  vector_computed_at?: string;
}

/** 하이라이트 */
export interface Highlight {
  id: string;
  user_book_id: string;
  content: string;
  note?: string;
  page?: number;
  created_at: string;
}

/** 유저 정보 */
export interface User {
  id: string;
  email: string;
  name: string;
  profile_image?: string;
}

/** CSV 임포트 결과 */
export interface ImportResult {
  total: number;
  created: number;
  skipped: number;
  failed: number;
  errors: string[];
}
