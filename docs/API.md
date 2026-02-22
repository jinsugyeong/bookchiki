# API 엔드포인트 레퍼런스

마지막 업데이트: 2026-02-22 (Phase 4 자연어 검색 및 books 인덱싱 제거 완료)

이 문서는 Bookchiki 백엔드의 모든 API 엔드포인트를 설명합니다.

---

## 기본 정보

- **Base URL:** `http://localhost:8000` (로컬 개발)
- **인증:** Bearer JWT 토큰 (대부분의 엔드포인트)
- **개발 환경:** `APP_ENV=development`일 때 Bearer 토큰 없이 요청 가능 (자동으로 `dev@bookchiki.local` 사용자 생성)
- **응답 형식:** JSON

---

## 인증 (Authentication)

### POST `/auth/google`

Google OAuth 인증 코드를 JWT 액세스 토큰으로 교환합니다.

**요청:**

```json
{
  "code": "4/0AY..."
}
```

**응답 (200):**

```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "name": "John Doe",
    "profile_image": "https://..."
  }
}
```

**주의:** 개발 환경에서는 이 엔드포인트를 사용할 필요 없습니다. Bearer 토큰 없이 다른 API를 호출하면 자동으로 인증됩니다.

---

### GET `/auth/me`

현재 인증된 사용자 정보를 반환합니다.

**응답 (200):**

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "name": "John Doe",
  "profile_image": "https://..."
}
```

---

## 도서 관리 (Books)

### GET `/books`

도서 목록을 조회합니다. 검색 필터링 지원.

**쿼리 파라미터:**

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `q` | String | 제목 또는 저자명 검색 (부분 일치) |
| `skip` | Integer | 페이지 오프셋 (기본값: 0) |
| `limit` | Integer | 페이지 크기 (기본값: 20, 최대: 50) |

**요청:**

```bash
GET /books?q=파이썬&skip=0&limit=20
```

**응답 (200):**

```json
[
  {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "title": "파이썬 완전정복",
    "author": "이순신",
    "isbn": "978-1234567890",
    "description": "파이썬 기초부터 고급까지...",
    "cover_image_url": "https://...",
    "genre": "프로그래밍",
    "published_at": "2023-01-15"
  }
]
```

---

### GET `/books/search/aladin`

알라딘 API를 통해 도서를 검색합니다.

**쿼리 파라미터:**

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `q` | String | 검색 쿼리 (필수) |
| `max_results` | Integer | 반환 결과 수 (기본값: 20, 1~50) |

**요청:**

```bash
GET /books/search/aladin?q=클린%20코드&max_results=10
```

**응답 (200):**

```json
[
  {
    "title": "클린 코드",
    "author": "Robert C. Martin",
    "isbn": "978-0132350884",
    "description": "A Handbook of Agile Software Craftsmanship",
    "cover_image_url": "https://...",
    "genre": "프로그래밍",
    "published_at": "2008-08-01"
  }
]
```

---

### POST `/books/search/aladin/select`

알라딘 검색 결과를 선택하여 도서 테이블에 저장합니다.

**요청:**

```json
{
  "title": "클린 코드",
  "author": "Robert C. Martin",
  "isbn": "978-0132350884",
  "description": "...",
  "cover_image_url": "https://...",
  "genre": "프로그래밍",
  "published_at": "2008-08-01"
}
```

**응답 (201):**

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174001",
  "title": "클린 코드",
  "author": "Robert C. Martin",
  "isbn": "978-0132350884",
  "description": "...",
  "cover_image_url": "https://...",
  "genre": "프로그래밍",
  "published_at": "2008-08-01",
  "created_at": "2026-02-22T10:00:00Z"
}
```

**동작:**
- ISBN 또는 제목+저자 조합으로 중복 체크
- 신규 도서면 도서 테이블 저장

---

### GET `/books/{book_id}`

특정 도서를 조회합니다.

**응답 (200):**

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "파이썬 완전정복",
  "author": "이순신",
  "isbn": "978-1234567890",
  "description": "...",
  "cover_image_url": "https://...",
  "genre": "프로그래밍",
  "published_at": "2023-01-15",
  "created_at": "2026-02-20T08:00:00Z"
}
```

---

### POST `/books`

새 도서를 수동으로 추가합니다.

**요청:**

```json
{
  "title": "새로운 책",
  "author": "저자명",
  "isbn": "978-XXXXXXXXXX",
  "description": "도서 설명",
  "cover_image_url": "https://...",
  "genre": "장르",
  "published_at": "2023-01-15"
}
```

**응답 (201):** 생성된 도서 객체

---

## 내 서재 (My Books)

### GET `/my-books/stats`

현재 사용자의 독서 통계를 조회합니다.

**응답 (200):**

```json
{
  "total_books": 50,
  "books_read": 30,
  "books_reading": 5,
  "books_wishlist": 15,
  "average_rating": 4.2,
  "genre_distribution": {
    "소설": 15,
    "자기계발": 8,
    "역사": 7
  },
  "monthly_counts": {
    "2026-01": 3,
    "2026-02": 5
  }
}
```

---

### GET `/my-books`

현재 사용자의 도서 목록을 조회합니다.

**쿼리 파라미터:**

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `status` | String | 상태 필터 (`read`, `reading`, `wishlist`) |
| `skip` | Integer | 페이지 오프셋 (기본값: 0) |
| `limit` | Integer | 페이지 크기 (기본값: 20) |

**요청:**

```bash
GET /my-books?status=read&limit=10
```

**응답 (200):**

```json
[
  {
    "id": "user-book-id-1",
    "user_id": "user-id",
    "book_id": "book-id-1",
    "book": {
      "id": "book-id-1",
      "title": "클린 코드",
      "author": "Robert C. Martin",
      "isbn": "978-0132350884",
      "genre": "프로그래밍",
      "cover_image_url": "https://...",
      "description": "..."
    },
    "status": "read",
    "rating": 5,
    "memo": "정말 좋은 책!",
    "source": "manual",
    "created_at": "2026-02-01T10:00:00Z",
    "finished_at": "2026-02-10T18:00:00Z"
  }
]
```

---

### POST `/my-books`

현재 사용자의 서재에 도서를 추가합니다.

**요청:**

```json
{
  "book_id": "book-id-1",
  "status": "reading",
  "rating": null,
  "memo": ""
}
```

**응답 (201):** 생성된 UserBook 객체

**주의:**
- 동일 도서를 중복으로 추가할 수 없습니다. (409 Conflict)
- 도서 추가 시 `user_preference_profiles`의 `is_dirty` 플래그가 자동으로 true로 설정됩니다. (`dirty_reason='book_added'`)

---

### PATCH `/my-books/{user_book_id}`

서재의 도서 정보를 업데이트합니다 (상태, 별점, 메모 등).

**요청:**

```json
{
  "status": "read",
  "rating": 4,
  "memo": "흥미로운 내용이었다.",
  "finished_at": "2026-02-22T18:00:00Z"
}
```

**응답 (200):** 업데이트된 UserBook 객체

**주의:** 모든 필드 변경 시 `user_preference_profiles`의 `is_dirty` 플래그가 자동으로 true로 설정됩니다. (기존: rating만 캐시 무효화)

---

### DELETE `/my-books/{user_book_id}`

서재에서 도서를 제거합니다.

**응답 (204):** No Content

**주의:** 도서 삭제 시 `user_preference_profiles`의 `is_dirty` 플래그가 자동으로 true로 설정됩니다. (`dirty_reason='book_deleted'`)

---

## 하이라이트 & 메모 (Highlights)

### GET `/highlights`

현재 사용자의 하이라이트/메모를 조회합니다.

**쿼리 파라미터:**

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `user_book_id` | UUID | UserBook ID로 필터링 |
| `skip` | Integer | 페이지 오프셋 (기본값: 0) |
| `limit` | Integer | 페이지 크기 (기본값: 50) |

**응답 (200):**

```json
[
  {
    "id": "highlight-id-1",
    "user_book_id": "user-book-id-1",
    "content": "좋은 코드는 다른 사람이 읽을 때...",
    "note": "핵심 표현",
    "page": 42,
    "created_at": "2026-02-15T14:30:00Z"
  }
]
```

---

### POST `/highlights`

새 하이라이트/메모를 추가합니다.

**요청:**

```json
{
  "user_book_id": "user-book-id-1",
  "content": "좋은 코드는 다른 사람이 읽을 때...",
  "note": "핵심 표현",
  "page": 42
}
```

**응답 (201):** 생성된 Highlight 객체

---

### PATCH `/highlights/{highlight_id}`

하이라이트를 업데이트합니다.

**요청:**

```json
{
  "note": "수정된 메모",
  "page": 43
}
```

**응답 (200):** 업데이트된 Highlight 객체

---

### DELETE `/highlights/{highlight_id}`

하이라이트를 삭제합니다.

**응답 (204):** No Content

---

## 추천 (Recommendations)

### GET `/recommendations`

현재 사용자의 개인화된 도서 추천을 조회합니다. (기록 기반)

**쿼리 파라미터:**

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `limit` | Integer | 반환 추천 수 (기본값: 10, 1~50) |

**요청:**

```bash
GET /recommendations?limit=10
```

**응답 (200):**

```json
{
  "recommendations": [
    {
      "book_id": "book-id-1",
      "title": "도메인 주도 설계",
      "author": "Eric Evans",
      "description": "...",
      "genre": "프로그래밍",
      "cover_image_url": "https://...",
      "mood": "깊이 있는",
      "score": 0.87,
      "reason": "당신이 좋아하는 '클린 코드'와 유사한 주제의 책입니다."
    }
  ],
  "total": 10,
  "cache_status": "hit",
  "profile_version": 3,
  "profile_computed_at": "2026-02-22T10:00:00Z"
}
```

**동작:**
1. `user_preference_profiles`에서 `is_dirty` 플래그 확인
   - `is_dirty=false` → `recommendations` 테이블 직접 SELECT (캐시 히트, ~10ms)
   - `is_dirty=true` → 전체 파이프라인 실행 (캐시 미스, 30~60초)
2. 사용자 라이브러리 + 메모 분석 → 취향 프로필 생성 (LLM)
3. 취향 벡터 계산 (OpenAI embed)
4. GPT-4o-mini로 책 후보 생성
5. 알라딘 API로 실존 검증
6. 취향 벡터로 재랭킹
7. 최종 N권만 DB + OpenSearch 저장
8. `user_preference_profiles` 갱신 (`is_dirty=false`, `profile_data`, `preference_vector`)

**주의:** Cold start(평점 없음) 사용자는 별점 가중치 없이 추천됩니다.

---

### POST `/recommendations/ask` (시스템 2 — 질문 기반 맞춤 추천)

저장된 취향 프로필과 커뮤니티 지식 베이스를 활용하여 자유 질문에 맞는 맞춤 추천을 제공합니다.

**요청:**

```json
{
  "question": "감동적인 가족 이야기 추천해줘"
}
```

**응답 (200):**

```json
{
  "recommendations": [
    {
      "book_id": "book-id-1",
      "title": "파친코",
      "author": "이민진",
      "description": "...",
      "genre": "소설",
      "cover_image_url": "https://...",
      "score": 0.92,
      "reason": "당신의 취향(심리 묘사가 섬세한 소설 선호)과 요청하신 '감동적인 가족 이야기'를 완벽하게 만족하는 책입니다."
    }
  ],
  "total": 10
}
```

**동작:**
1. 저장된 `user_preference_profiles.profile_data` 조회 (is_dirty 무관)
2. `rag_knowledge` 인덱스에서 사용자 질문과 관련된 정보 하이브리드 검색
3. LLM에 다음을 컨텍스트로 주입:
   - 취향 프로필: `preference_summary`, `preferred_genres`, `disliked_genres`, `top_rated_books`
   - 검색 결과 (커뮤니티 데이터 청크)
4. 사용자 질문 + 취향 프로필 + 검색 결과를 종합하여 맞춤 추천 생성
5. 캐시 overwrite 없음 (별도 응답)

**주의:** 캐시를 수정하지 않으므로 여러 번 질문 가능.

---

### GET `/recommendations/profile` (신규)

현재 사용자의 취향 프로필을 조회합니다. (디버그/UI용)

**응답 (200):**

```json
{
  "profile_data": {
    "preferred_genres": ["한국소설", "SF"],
    "disliked_genres": ["자기계발"],
    "preference_summary": "심리 묘사가 섬세하고 세계관이 독창적인 소설을 선호합니다.",
    "top_rated_books": [
      {"title": "파친코", "author": "이민진", "rating": 5},
      {"title": "채식주의자", "author": "한강", "rating": 5}
    ],
    "reading_count": 42,
    "memo_analyzed_at": "2026-02-22T10:00:00Z"
  },
  "is_dirty": false,
  "dirty_reason": null,
  "version": 3,
  "profile_computed_at": "2026-02-22T10:00:00Z",
  "vector_computed_at": "2026-02-22T10:00:00Z"
}
```

**동작:**
- 사용자의 `user_preference_profiles` 레코드 조회
- is_dirty=true인 경우 "캐시 재생성 필요" 알림
- 프로필 버전 및 마지막 계산 시각 반환

---

### POST `/recommendations/refresh` (신규)

추천 캐시를 무시하고 새로운 추천을 생성합니다. (강제 갱신)

**쿼리 파라미터:**

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `limit` | Integer | 반환 추천 수 (기본값: 10, 1~50) |

**응답 (200):**

```json
{
  "recommendations": [...],
  "cache_status": "refreshed",
  "profile_version": 4,
  "profile_computed_at": "2026-02-22T11:00:00Z"
}
```

**동작:**
- `is_dirty` 플래그와 무관하게 파이프라인 강제 실행
- 새로운 추천 결과 생성 + `user_preference_profiles` 갱신

---


## CSV 가져오기 (Imports)

### POST `/imports/csv`

북적북적 등 외부 앱의 CSV 파일을 가져옵니다.

**요청 (multipart/form-data):**

```bash
curl -X POST http://localhost:8000/imports/csv \
  -H "Authorization: Bearer token" \
  -F "file=@books.csv"
```

**응답 (200):**

```json
{
  "imported_count": 15,
  "skipped_count": 3,
  "errors": [
    "Row 5: ISBN 필드 누락"
  ],
  "message": "15개의 도서를 가져왔습니다."
}
```

**지원 형식:**
- 북적북적 앱 CSV (한국어 컬럼명)

**동작:**
1. CSV 파싱 (한국어 컬럼명 매핑)
2. 알라딘 API로 누락 정보 보강
3. ISBN 또는 (제목, 저자) 중복 제거
4. 도서 저장
5. `user_preference_profiles`의 `is_dirty` 플래그 설정 (`dirty_reason='csv_imported'`)

---

## 관리자 (Admin)

### POST `/admin/seed-community-books`

커뮤니티 데이터 (독서 기록, 추천 정보 등)를 파싱하여 도서 데이터베이스에 시딩합니다.

**응답 (200):**

```json
{
  "total_books_seeded": 450,
  "message": "Successfully seeded 450 books from community data."
}
```

**주의:**
- 관리자 전용 (차후 권한 검증 추가 예정)
- 알라딘 API 호출로 비용 발생 (책 실존 검증)
- 대량 도서 시딩 시 시간이 오래 걸릴 수 있음 (동시 요청 제한: 5개)

---

## 에러 응답

모든 에러 응답은 다음 형식입니다:

```json
{
  "detail": "에러 메시지"
}
```

| HTTP 상태 | 설명 |
|---------|------|
| 400 | Bad Request (검증 실패) |
| 401 | Unauthorized (토큰 없음 또는 만료) |
| 403 | Forbidden (권한 없음) |
| 404 | Not Found (리소스 없음) |
| 409 | Conflict (중복 데이터) |
| 500 | Internal Server Error |

---

## API 문서 도구

백엔드 실행 중:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## 참고

- [CONTRIBUTING.md](./CONTRIBUTING.md) — 개발 환경 세팅
- [ENV.md](./ENV.md) — 환경변수 설정
- [CLAUDE.md](../CLAUDE.md) — 아키텍처 상세 설명
