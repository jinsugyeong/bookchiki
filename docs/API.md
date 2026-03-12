# API 엔드포인트 레퍼런스

마지막 업데이트: 2026-03-12

이 문서는 Bookchiki 백엔드의 모든 API 엔드포인트를 설명합니다.

---

## 기본 정보

- **Base URL:** `http://localhost:8000` (로컬 개발)
- **인증:** Bearer JWT 액세스 토큰 (대부분의 엔드포인트)
- **토큰 만료:** 액세스 토큰 기본 15분, Refresh Token 기본 7일
- **응답 형식:** JSON

---

## 인증 (Authentication)

### POST `/auth/google` **Google Login**

Google OAuth 인증 코드를 JWT 액세스 토큰 + Refresh Token으로 교환합니다.

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
  "refresh_token": "uuid-token-string",
  "token_type": "bearer",
  "user": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "name": "John Doe",
    "profile_image": "https://..."
  }
}
```

**동작:**
- Google OAuth 코드를 Google API와 교환
- 신규 사용자면 DB에 생성, 기존 사용자면 조회
- Access Token (15분 기본) + Refresh Token (7일 기본) 발급
- Refresh Token은 `refresh_tokens` 테이블에 저장

---

### POST `/auth/refresh` **Refresh Access Token**

Refresh Token으로 새 Access Token을 발급받습니다.

**요청:**

```json
{
  "refresh_token": "uuid-token-string"
}
```

**응답 (200):**

```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer"
}
```

**동작:**
- Refresh Token 유효성 검증 (DB 확인 + 만료 시간 확인)
- 새 Access Token 발급
- 이전 Refresh Token은 자동 폐기, 새 Refresh Token 발급 (토큰 회전)

**에러:**
- `401 Unauthorized` — Refresh Token 없음, 폐기됨, 또는 만료됨

---

### POST `/auth/logout` **Logout**

Refresh Token을 폐기(revoke)하여 로그아웃 처리.

**요청 헤더:**
```
Authorization: Bearer {access_token}
```

**요청:**

```json
{
  "refresh_token": "uuid-token-string"
}
```

**응답 (204):** No Content

**동작:**
- 사용자의 해당 Refresh Token을 폐기(revoke)합니다.
- Access Token은 클라이언트에서 삭제해야 합니다.

---

### GET `/auth/me` **Get Me**

현재 인증된 사용자 정보를 반환합니다.

**요청 헤더:**
```
Authorization: Bearer {access_token}
```

**응답 (200):**

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "name": "John Doe",
  "profile_image": "https://...",
  "instagram_username": "bookstagram_id"
}
```

---

### PATCH `/auth/me` **Update Me**

현재 로그인한 사용자 프로필 업데이트 (인스타그램 계정명 등).

**요청 헤더:**
```
Authorization: Bearer {access_token}
```

**요청:**

```json
{
  "instagram_username": "new_instagram_id"
}
```

**응답 (200):** 업데이트된 사용자 객체 (`UserResponse`)

**동작:**
- 인스타그램 계정명 등 사용자 정보를 수정합니다.

---

### DELETE `/auth/me` **Delete Me**

현재 로그인한 사용자의 계정을 탈퇴(비활성화) 처리합니다.

**요청 헤더:**
```
Authorization: Bearer {access_token}
```

**응답 (204):** No Content

**동작:**
- 사용자의 개인정보(이메일, 이름, 프로필 이미지 등)를 익명화하거나 삭제합니다.
- 모든 Refresh Token을 폐기하여 즉시 로그아웃 처리합니다.
- 계정을 `is_active=False`로 설정하여 비활성화합니다.
- 단, 추천 시스템의 데이터 품질 유지를 위해 독서 기록(`user_books`) 등 활동 내역은 익명화된 상태로 보존될 수 있습니다.

---



## 도서 관리 (Books)

### GET `/books` **List Books**

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
    "publisher": "한빛미디어",
    "published_at": "2023-01-15"
  }
]
```

---

### GET `/books/search/aladin` **Search Aladin**

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
    "publisher": "인사이트",
    "published_at": "2008-08-01"
  }
]
```

---

### POST `/books/search/aladin/select` **Select Aladin Book**

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
  "publisher": "인사이트",
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
  "publisher": "인사이트",
  "published_at": "2008-08-01",
  "created_at": "2026-02-22T10:00:00Z"
}
```

**동작:**
- ISBN 또는 제목+저자 조합으로 중복 체크
- 신규 도서면 도서 테이블 저장 및 OpenSearch `books` 인덱스 실시간 반영

---

### GET `/books/{book_id}` **Get Book**

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
  "publisher": "한빛미디어",
  "published_at": "2023-01-15",
  "created_at": "2026-02-20T08:00:00Z"
}
```

---

### POST `/books` **Create Book**

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
  "publisher": "출판사명",
  "published_at": "2023-01-15"
}
```

**응답 (201):** 생성된 도서 객체

---

## 내 서재 (My Books)

### GET `/my-books/stats` **Get Reading Stats**

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

### GET `/my-books` **List My Books**

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
      "publisher": "인사이트",
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

### POST `/my-books` **Add Book**

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
- 사용자가 과거에 이 책을 "다른 책(dismiss)" 처리했던 기록이 있다면, 서재 추가 시 해당 기록이 자동으로 삭제됩니다.

---

### PATCH `/my-books/{user_book_id}` **Update My Book**

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

**주의:**
- 업데이트 시 OpenSearch `user_books` 인덱스에 실시간 반영됩니다.
- `user_preference_profiles`의 `is_dirty` 플래그가 자동으로 true로 설정됩니다.

---

### DELETE `/my-books/{user_book_id}` **Delete My Book**

서재에서 도서를 제거합니다.

**응답 (204):** No Content

**주의:**
- 삭제 시 OpenSearch `user_books` 인덱스에서 해당 데이터가 즉시 삭제됩니다.
- `user_preference_profiles`의 `is_dirty` 플래그가 자동으로 true로 설정됩니다.

---

## 하이라이트 & 메모 (Highlights)

### GET `/highlights` **List Highlights**

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

### POST `/highlights` **Create Highlight**

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

### PATCH `/highlights/{highlight_id}` **Update Highlight**

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

### DELETE `/highlights/{highlight_id}` **Delete Highlight**

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
      "score": 0.87,
      "reason": "당신이 좋아하는 '클린 코드'와 유사한 주제의 책입니다."
    }
  ],
  "total": 10
}
```

**동작:**
1. `user_preference_profiles`에서 `is_dirty` 플래그 확인
   - `is_dirty=false` → `recommendations` 테이블 직접 SELECT (캐시 히트)
   - `is_dirty=true` → 전체 파이프라인 실행 (캐시 미스)
2. 서재 + dismissed 책 제외 목록 구성
3. 취향 벡터 계산 (평점 가중치 + 메모 임베딩 결합)
4. OpenSearch 하이브리드 검색 (BM25 + k-NN)
5. **알라딘 실시간 보완:** DB 외부의 실존 도서 검색 및 추가
6. **ALS CF 앙상블 스코어링:** 협업 필터링 모델 점수와 앙상블 (서재 규모에 따라 가중치 동적 조절)
7. 다양성 보장 (동일 장르 제한 + 가우시안 노이즈)
8. 최종 결과 캐시 저장 및 GPT-4o-mini 추천 이유 생성

---

### POST `/recommendations/ask` (시스템 2 — 질문 기반 맞춤 추천)

취향 프로필, 도서 지식 베이스(RAG), 그리고 **실시간 웹 검색(Tavily API)**을 결합하여 자유 질문에 맞는 **검증된 실존 도서**를 추천합니다.

**요청:**

```json
{
  "question": "감동적인 가족 이야기 추천해줘",
  "limit": 3
}
```

**응답 (200):**

```json
{
  "results": [
    {
      "book_id": "book-id-1",
      "title": "파친코",
      "author": "이민진",
      "reason": "당신의 취향(심리 묘사가 섬세한 소설 선호)과 요청하신 '감동적인 가족 이야기'를 완벽하게 만족하는 책입니다.",
      "isbn": "9791191114225",
      "cover_image_url": "https://...",
      "genre": "소설",
      "description": "..."
    }
  ],
  "total": 3,
  "question": "감동적인 가족 이야기 추천해줘"
}
```

**동작:**
1. 취향 프로필 및 RAG 지식 검색
2. **Tavily 실시간 웹 검색**으로 외부 도서 후보 확보
3. LLM이 후보군 중 질문에 가장 적합한 도서 선별
4. **알라딘 엄격 검증 (Strict Validation):** 선별된 도서가 실제로 존재하는지 알라딘 API로 교차 확인
5. 실존 확인된 도서만 최종 결과에 포함 (최대 `limit`개)
6. 추천 이력은 `ask_history` 테이블에 자동 저장됩니다.

---

### GET `/recommendations/profile`

현재 사용자의 취향 프로필 정보를 조회합니다. (디버그/UI용)

**응답 (200):**

```json
{
  "profile_data": {
    "preferred_genres": ["한국소설", "SF"],
    "disliked_genres": ["자기계발"],
    "preference_summary": "심리 묘사가 섬세하고 세계관이 독창적인 소설을 선호합니다.",
    "top_rated_books": [
      {"title": "파친코", "author": "이민진", "rating": 5}
    ],
    "reading_count": 42
  },
  "is_dirty": false,
  "updated_at": "2026-02-22T10:00:00Z"
}
```

---

### POST `/recommendations/refresh`

추천 캐시를 무시하고 새로운 추천을 강제 생성합니다.

**응답 (200):** `RecommendationListResponse` (GET /recommendations와 동일 형식)

---

### POST `/recommendations/dismiss/{book_id}`

추천 책을 영구 비추천 처리합니다. ("다른 책" 버튼)

**응답 (204):** No Content

**동작:**
- `user_dismissed_books`에 영구 저장하며, 현재 추천 캐시에서 즉시 제거합니다.
- 이후 모든 추천 파이프라인에서 해당 도서(및 동일 ISBN 도서)가 제외됩니다.

---

## 이미지 생성 (Images)

### GET `/images/daily-remaining`

현재 사용자의 오늘 남은 AI 배경 이미지 생성 횟수를 조회합니다.

**응답 (200):**

```json
{
  "remaining": 2,
  "limit": 3
}
```

---

### POST `/images/generate-background`

DALL-E 3를 사용하여 책 분위기에 맞는 AI 배경 이미지를 생성합니다.

**요청:**

```json
{
  "book_id": "book-id-1",
  "title": "클린 코드",
  "author": "Robert C. Martin",
  "genre": "프로그래밍",
  "description": "애자일 소프트웨어 장인 정신..."
}
```

**응답 (200):**

```json
{
  "image_url": "https://openai-generated-url...",
  "remaining_today": 1
}
```

---

## CSV 가져오기 (Imports)

### POST `/imports/csv`

북적북적 등 외부 앱의 CSV 파일을 가져옵니다.

**요청 (multipart/form-data):** `file=@books.csv`

**응답 (200):**

```json
{
  "imported_count": 15,
  "skipped_count": 3,
  "errors": ["Row 5: ISBN 필드 누락"],
  "message": "15개의 도서를 가져왔습니다."
}
```

---

## 관리자 (Admin)

### POST `/admin/seed-books`

외부 도서 데이터를 파싱하여 도서 데이터베이스에 시딩합니다.

**응답 (200):** `{"total": 450, "seeded": 420, "skipped": 30, "errors": 0}`

---

### POST `/admin/index-books`

DB의 모든 도서를 OpenSearch `books` 인덱스에 적재합니다.

**응답 (200):** `{"indexed": 480, "failed": 0, "total_tokens": 12500}`

---

### POST `/admin/index-user-books`

사용자 평점·메모를 OpenSearch `user_books` 인덱스에 적재합니다.

**응답 (200):** `{"indexed": 195, "failed": 0, "skipped": 5, "total_tokens": 8400}`

---

### POST `/admin/index-knowledge`

추천 참고 지식 데이터를 OpenSearch `rag_knowledge` 인덱스에 적재합니다.

**응답 (200):** `{"total": 100, "indexed": 100, "skipped": 0, "errors": 0, "source_stats": {...}}`

---

### GET `/admin/ask-history`

모든 사용자의 질문 기반 추천 이력을 조회합니다.

**응답 (200):**

```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "question": "질문 내용",
    "results": [...],
    "created_at": "2026-03-11T12:00:00Z"
  }
]
```


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
