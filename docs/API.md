# API 엔드포인트 레퍼런스

마지막 업데이트: 2026-03-09 (Dismiss 기능 + 알라딘 실시간 보완 + 자정 배치 스케줄러 추가)

이 문서는 Bookchiki 백엔드의 모든 API 엔드포인트를 설명합니다.

---

## 기본 정보

- **Base URL:** `http://localhost:8000` (로컬 개발)
- **인증:** Bearer JWT 액세스 토큰 (대부분의 엔드포인트)
- **토큰 만료:** 액세스 토큰 기본 60분, Refresh Token 기본 7일
- **응답 형식:** JSON

---

## 인증 (Authentication)

### POST `/auth/google`

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
- Access Token (60분 기본) + Refresh Token (7일 기본) 발급
- Refresh Token은 `refresh_tokens` 테이블에 저장

---

### POST `/auth/refresh`

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

### GET `/auth/me`

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
  "profile_image": "https://..."
}
```

---

### POST `/auth/logout`

로그아웃 및 Refresh Token 폐기.

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

**응답 (200):**

```json
{
  "message": "로그아웃되었습니다"
}
```

**동작:**
- 사용자의 모든 Refresh Token 폐기 (또는 특정 토큰만 폐기)
- Access Token은 클라이언트에서 삭제

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
   - `is_dirty=false` → `recommendations` 테이블 직접 SELECT (캐시 히트, ~10ms, ISBN 이중 필터)
   - `is_dirty=true` → 전체 파이프라인 실행 (캐시 미스)
2. 서재 + dismissed 책 제외 목록 구성
   - book_id + ISBN 이중 exclude로 서재/dismissed 책 영구 필터
   - dismissed된 책도 이후 추천에서 영구 제외
3. 취향 벡터 계산:
   - `user_books` OpenSearch 인덱스 단일 쿼리로 상호작용 데이터 전체 조회
     - `book_embedding` + `rating` → 평점 가중 성분
     - `memo_embedding` (not null인 것만) → 메모 선호 신호
   - `α × 평점가중_책임베딩 + (1-α) × 메모평균_임베딩` (α=0.6)
4. 선호 장르 키워드 추출
5. `books` OpenSearch 인덱스 하이브리드 검색 (BM25 + k-NN, 최대 `limit - 2` 개)
   - BM25: 선호 장르 키워드
   - k-NN: 취향 벡터 유사도
   - book_id + ISBN 이중으로 서재/dismissed 책 제외
6. **알라딘 실시간 보완** (신규)
   - OpenSearch에서 부족한 수만큼 알라딘 API 검색
   - ISBN 기반 중복 체크 (서재/dismissed 책 제외)
   - DB 밖 책도 추천 가능 → 신규 책 자동 저장 + 백그라운드 OpenSearch 인덱싱
   - 항상 최소 2슬롯 확보 (`_ALADIN_SLOTS`)
7. **CF 앙상블 스코어링** (Phase 4.3)
   - ALS 협업 필터링 모델에서 후보 도서 점수 조회
   - 최종 점수 = `α_ensemble × OpenSearch점수 + (1-α_ensemble) × CF점수`
   - α_ensemble 동적 조절: 서재 < 10권 → 0.9, 10-29권 → 0.7, ≥ 30권 → 0.5
   - CF 모델 없으면 원본 OpenSearch 점수 유지 (graceful degradation)
8. 다양성 보장 + score 정규화
   - 동일 장르 최대 2권, Gaussian 노이즈로 매번 다른 추천 생성
   - score 범위 정규화: [0.80, 1.00]
9. 최종 N권 `recommendations` 테이블 저장
10. `user_preference_profiles` 갱신 (`is_dirty=false`, `profile_data`, `preference_vector`)
11. GPT-4o-mini로 추천 이유 병렬 생성 (asyncio.gather)

**주의:** Cold start(평점/메모 없음) 사용자는 `books` 인덱스에서 description 기준 폴백 검색으로 추천됩니다. Dismissed 책은 이후 모든 추천에서 완벽하게 제외됩니다.

---

### POST `/recommendations/ask` (시스템 2 — 질문 기반 맞춤 추천)

저장된 취향 프로필과 도서 지식 베이스를 활용하여 자유 질문에 맞는 맞춤 추천을 제공합니다.

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
   - 검색 결과 (지식 베이스 청크)
4. 사용자 질문 + 취향 프로필 + 검색 결과를 종합하여 맞춤 추천 생성
5. 알라딘 API로 결과 검증 후 DB 저장 (book_id 확보) — "읽고 싶어요" 버튼 작동 가능
6. 서재 + dismissed ISBN/book_id 제외 처리
7. 최종 결과 반환 (캐시 overwrite 없음)

**주의:** 캐시를 수정하지 않으므로 여러 번 질문 가능. 추천 결과에서 "읽고 싶어요" 버튼 클릭 시 서재에 추가됨.

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

### POST `/recommendations/dismiss/{book_id}` (신규)

추천 책을 영구 비추천 처리합니다. ("다른 책" 버튼)

**요청 경로 파라미터:**

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `book_id` | UUID | 비추천할 도서 ID |

**응답 (200):**

```json
{
  "message": "도서가 영구 비추천 처리되었습니다.",
  "book_id": "book-id-1"
}
```

**동작:**
1. `user_dismissed_books` 테이블에 사용자-도서 쌍 저장
2. `recommendations` 캐시 테이블에서 해당 도서 즉시 삭제
3. 멱등 처리 (이미 dismiss된 경우 무시)
4. 이후 모든 추천(`GET /recommendations`, `POST /recommendations/ask`)에서 ISBN/book_id 기반으로 영구 제외

**주의:**
- 삭제 후 새로고침해도 동일 도서는 다시 나타나지 않습니다.
- 사용자가 서재에 다시 추가한 경우 dismissed 레코드 자동 삭제는 아직 구현 안됨 (향후 개선 예정)

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

### POST `/admin/seed-books`

외부 도서 데이터를 파싱하여 도서 데이터베이스에 시딩합니다.

**응답 (200):**

```json
{
  "total_books_seeded": 450,
  "message": "Successfully seeded 450 books from data."
}
```

**주의:**
- 관리자 전용 (차후 권한 검증 추가 예정)
- 알라딘 API 호출로 비용 발생 (책 실존 검증)
- 대량 도서 시딩 시 시간이 오래 걸릴 수 있음 (동시 요청 제한: 5개)

---

### POST `/admin/index-books`

DB `books` 테이블의 모든 도서를 OpenSearch `books` 인덱스에 임베딩하여 적재합니다.

**응답 (200):**

```json
{
  "total": 500,
  "indexed": 480,
  "skipped": 20,
  "errors": 0
}
```

**주의:**
- 관리자 전용
- OpenAI API 임베딩 호출로 비용 발생 (책 수에 비례)
- 이미 인덱싱된 book_id는 스킵 (중복 방지)
- 실행 전 사용자 확인 필요

---

### POST `/admin/index-user-books`

`user_books` 테이블의 평점·메모 데이터를 OpenSearch `user_books` 인덱스에 임베딩하여 적재합니다. `book_embedding`(책 내용)과 `memo_embedding`(메모 텍스트)을 함께 저장하여 취향 벡터 계산 시 단일 쿼리로 조회 가능합니다.

**응답 (200):**

```json
{
  "total": 200,
  "indexed": 195,
  "skipped": 5,
  "errors": 0
}
```

**주의:**
- 관리자 전용
- OpenAI API 임베딩 호출로 비용 발생 (메모 있는 항목만 memo_embedding 생성)
- 평점도 메모도 없는 UserBook은 스킵
- 실행 전 사용자 확인 필요

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
