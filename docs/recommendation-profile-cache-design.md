# 추천 시스템 — 취향 프로필 캐싱 아키텍처 설계

> **작성일:** 2026-02-22
> **브랜치:** `feature/llm-recommendation-pipeline`
> **목적:** 인메모리 캐시(TTL 기반)를 DB 영속화 + 이벤트 기반 캐시 무효화로 전환

---

## 1. 현재 시스템의 문제점

| 문제 | 설명 |
|------|------|
| 인메모리 캐시 휘발 | 프로세스 재시작 시 캐시 소멸 → 불필요한 LLM API 재호출 |
| TTL 기반 무효화 | 독서 기록 변경과 무관하게 1시간마다 재생성 |
| 불완전한 무효화 | 평점 변경 시만 캐시 삭제 — 책 추가/삭제/메모 변경/CSV 임포트 시 미작동 |
| 취향 프로필 비영속 | 메모 분석 결과도 인메모리 — 2시간 TTL |

---

## 2. 새로운 설계 목표

1. **즉시 응답**: 페이지 접속 시 DB에서 캐싱된 추천 결과 즉시 반환
2. **이벤트 기반 무효화**: TTL 제거 → 독서 기록 변경 시에만 재생성
3. **취향 프로필 영속화**: PostgreSQL에 유저 취향 프로필 저장 (프로세스 재시작에도 유지)
4. **질문 기반 추천 지원**: 저장된 취향 프로필을 LLM 컨텍스트로 재활용

---

## 3. 새 DB 스키마

### 3-1. `user_preference_profiles` (신규 테이블)

```sql
CREATE TABLE user_preference_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,

    -- 취향 프로필 데이터 (JSONB)
    profile_data    JSONB NOT NULL DEFAULT '{}',
    -- {
    --   "preferred_genres": ["한국소설", "SF"],
    --   "disliked_genres": ["자기계발"],
    --   "preference_summary": "심리 묘사가 섬세한 소설을 선호하며...",
    --   "top_rated_books": [{"title": "...", "author": "...", "rating": 5}],
    --   "reading_count": 42
    -- }

    -- 취향 벡터 (OpenAI 1536차원, JSON 배열로 저장)
    preference_vector   JSONB,          -- null이면 cold start (평점 없음)

    -- 더티 플래그
    is_dirty        BOOLEAN NOT NULL DEFAULT TRUE,
    dirty_reason    VARCHAR(100),       -- 'book_added' | 'book_updated' | 'book_deleted' | 'csv_imported'

    -- 낙관적 동시성 제어
    version         INTEGER NOT NULL DEFAULT 0,

    -- 타임스탬프
    profile_computed_at     TIMESTAMPTZ,    -- 마지막 프로필 계산 시각
    vector_computed_at      TIMESTAMPTZ,    -- 마지막 벡터 계산 시각
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_user_preference_profiles_user_id ON user_preference_profiles(user_id);
```

### 3-2. `recommendations` 테이블 — 변경 없음

기존 스키마를 그대로 사용. `recommendations` 테이블이 곧 "추천 결과 캐시" 역할을 함.

```sql
-- 기존 유지
recommendations: id, user_id, book_id, score, reason, created_at
```

> **설계 결정**: 별도 캐시 테이블 없이 `recommendations` + `user_preference_profiles.is_dirty` 조합으로 캐시 상태 관리.

---

## 4. `profile_data` JSONB 상세 구조

```json
{
  "preferred_genres": ["한국소설", "SF", "추리"],
  "disliked_genres": ["자기계발"],
  "preference_summary": "심리 묘사가 섬세하고 세계관이 독창적인 소설을 선호함. 가볍고 교훈적인 자기계발서는 기피.",
  "top_rated_books": [
    {"title": "파친코", "author": "이민진", "rating": 5},
    {"title": "채식주의자", "author": "한강", "rating": 5}
  ],
  "reading_count": 42,
  "memo_analyzed_at": "2026-02-22T10:00:00Z"
}
```

---

## 5. 추천 흐름 설계

### 5-1. 기록 기반 추천 — 시스템 1 (메인 페이지 접속)

```
GET /recommendations
        │
        ▼
user_preference_profiles 조회
        │
   ┌────┴────┐
   │         │
is_dirty    is_dirty
= false     = true
   │         │
   ▼         ▼
recommendations  전체 파이프라인 실행
테이블 직접 SELECT   │
(~10ms, API 0회)    ├─ 1. 유저 서재 로드
        │           ├─ 2. 취향 벡터 계산
        │           │      - user_books 인덱스 단일 쿼리
        │           │        (book_embedding + rating + memo_embedding 한 번에 조회)
        │           │      - α × 평점가중_책임베딩 + (1-α) × 메모평균_임베딩
        │           ├─ 3. 장르 키워드 추출 (선호 장르)
        │           ├─ 4. OpenSearch books 인덱스 하이브리드 검색
        │           │      BM25(장르) + k-NN(취향벡터)
        │           │      이미 서재에 있는 책 제외
        │           ├─ 5. DB 저장 (recommendations)
        │           ├─ 6. user_preference_profiles 갱신
        │           │      is_dirty = false
        │           │      profile_data = {...}
        │           │      version += 1
        │           └─ 7. LLM으로 추천 이유 생성 + 응답
        │
        ▼
      응답
```

### 5-2. 질문 기반 추천 — 시스템 2

```
POST /recommendations/ask
{ "question": "감동적인 가족 이야기 추천해줘" }
        │
        ▼
1. 취향 프로필(profile_data) 및 RAG(OpenSearch) 컨텍스트 수집
        │
        ▼
2. 실시간 웹 검색 (Tavily API)
   - 질문 기반 최신/실존 도서 후보(Web Context) 확보
        │
        ▼
3. LLM 선별 호출 (Search-Augmented Generation)
   - 취향 + RAG + 웹 검색 결과를 종합하여 10권의 후보 선별
        │
        ▼
4. 알라딘 엄격 검증 (Strict Aladin Validation)
   - 제목+저자 기반 알라딘 API 검색 → 100% 실존 도서만 통과
        │
        ▼
5. 최종 3권 확정 및 응답 (캐시 overwrite 없음)
```

---

## 6. Dirty 마킹 전략

### 트리거 이벤트 (전체 4개)

| 엔드포인트 | 이벤트 | Dirty 마킹 |
|-----------|--------|------------|
| `POST /my-books` | 책 추가 | `is_dirty=true`, `dirty_reason='book_added'` |
| `PATCH /my-books/{id}` | 평점/메모/상태 변경 | `is_dirty=true`, `dirty_reason='book_updated'` |
| `DELETE /my-books/{id}` | 책 삭제 | `is_dirty=true`, `dirty_reason='book_deleted'` |
| `POST /imports/csv` | CSV 임포트 | `is_dirty=true`, `dirty_reason='csv_imported'` |

> **현재 버그 동시 수정**: 기존 `invalidate_cache`는 `PATCH` 중 rating 변경 시만 호출됨. 새 설계는 모든 변경 이벤트에서 dirty 마킹.

### Dirty 마킹 함수 설계

```
mark_profile_dirty(user_id, reason) → void
  1. user_preference_profiles에서 해당 유저 레코드 조회 (없으면 생성)
  2. is_dirty = TRUE, dirty_reason = reason, updated_at = NOW()
  3. DB commit
```

---

## 7. API 설계

### 변경되는 엔드포인트

| 메서드 | 경로 | 변경 내용 |
|--------|------|-----------|
| `GET` | `/recommendations` | 캐시 조회 로직 변경 (인메모리 → DB) |
| `POST` | `/my-books` | Dirty 마킹 추가 |
| `PATCH` | `/my-books/{id}` | Dirty 마킹 범위 확대 (rating만 → 모든 필드) |
| `DELETE` | `/my-books/{id}` | Dirty 마킹 추가 |
| `POST` | `/imports/csv` | Dirty 마킹 추가 |

### 신규 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `POST` | `/recommendations/ask` | 질문 기반 추천 |
| `GET` | `/recommendations/profile` | 유저 취향 프로필 조회 (디버그/UI용) |
| `POST` | `/recommendations/refresh` | 강제 추천 재생성 (`force_refresh=true` 대체) |

### `GET /recommendations` 응답 변경

```json
{
  "recommendations": [...],
  "cache_status": "hit",        // "hit" | "miss" | "refreshed"
  "profile_version": 3,
  "profile_computed_at": "2026-02-22T10:00:00Z"
}
```

---

## 8. 서비스 계층 설계

### 신규 파일: `backend/app/services/profile_cache.py`

```
역할:
  - mark_profile_dirty(user_id, reason) — dirty 마킹
  - get_or_create_profile(user_id) — 프로필 조회 or 신규 생성
  - update_profile(user_id, profile_data, preference_vector) — 프로필 갱신
  - is_recommendation_fresh(user_id) — 추천 결과가 최신인지 확인

의존성:
  - SQLAlchemy AsyncSession
  - UserPreferenceProfile 모델
```

### `recommend.py` 변경사항

```
제거:
  - _recommendation_cache (인메모리 dict)
  - _memo_analysis_cache (인메모리 dict)
  - CACHE_TTL_SECONDS, MEMO_CACHE_TTL_SECONDS
  - invalidate_cache() 함수

추가:
  - get_cached_recommendations(user_id, db) — DB에서 캐시 조회
  - save_profile_after_pipeline(user_id, profile_data, pref_vector, db) — 파이프라인 후 프로필 저장

수정:
  - get_recommendations() — 캐시 확인 로직을 DB 기반으로 교체
  - get_memo_analysis() — 인메모리 캐시 제거, profile_data에서 조회 우선
```

---

## 9. 영향받는 파일 목록

### 신규 생성 (2개)

| 파일 | 설명 |
|------|------|
| `backend/app/models/user_preference_profile.py` | UserPreferenceProfile SQLAlchemy 모델 |
| `backend/app/services/profile_cache.py` | 프로필 캐시 서비스 |

### 수정 (7개)

| 파일 | 주요 변경 |
|------|-----------|
| `backend/app/models/__init__.py` | UserPreferenceProfile import 추가 |
| `backend/app/models/user.py` | `preference_profile` relationship 추가 |
| `backend/app/services/recommend.py` | 인메모리 캐시 제거, DB 캐시 전환 |
| `backend/app/api/user_books.py` | dirty 마킹 확대 (add/update/delete) |
| `backend/app/api/imports.py` | CSV 임포트 후 dirty 마킹 추가 |
| `backend/app/api/recommendations.py` | 신규 엔드포인트 추가 (`/ask`, `/profile`, `/refresh`) |
| `backend/app/schemas/recommendation.py` | 응답 스키마에 cache_status, profile_version 추가 |

---

## 10. 마이그레이션 전략 (4단계)

### Step 1 — 모델 + Dirty 마킹 (코드 변경 최소화)
- `user_preference_profiles` 테이블 생성
- `mark_profile_dirty()` 함수 구현
- 기존 4개 API에 dirty 마킹 추가
- 인메모리 캐시 **병행 유지** (안전망)

### Step 2 — 추천 파이프라인 DB 캐시 전환
- `get_recommendations()` 캐시 확인 로직을 DB로 교체
- 파이프라인 실행 후 `user_preference_profiles` 갱신
- 인메모리 캐시 제거

### Step 3 — 질문 기반 추천 추가
- `POST /recommendations/ask` 구현
- `profile_data`를 LLM 컨텍스트로 주입하는 로직 구현

### Step 4 — 정리 및 최적화
- 레거시 코드 완전 제거 (`invalidate_cache`, 인메모리 dict)
- `force_refresh` 파라미터를 `/refresh` 엔드포인트로 이전
- Alembic 마이그레이션 파일 생성

---

## 11. 리스크 및 고려사항

| 리스크 | 심각도 | 완화 방법 |
|--------|--------|-----------|
| Cold start 지연 (첫 요청 30~60초) | MEDIUM | 프론트엔드에서 로딩 스피너 표시 + `/refresh` 백그라운드 호출 |
| 동시 dirty → 중복 파이프라인 실행 | MEDIUM | `version` 컬럼 낙관적 동시성 제어 |
| preference_vector 저장 크기 | LOW | 1536차원 × 4byte = ~6KB/유저, JSONB로 충분 |
| 기존 추천 결과 없는 유저 | LOW | `recommendations` 비어있으면 is_dirty=true로 처리 (자동 생성) |
| LLM/알라딘 API 장애 시 | MEDIUM | 기존 캐시 반환 (is_dirty 상태 유지, 재시도는 다음 요청) |

---

## 12. 예상 효과

| 지표 | 현재 | 개선 후 |
|------|------|---------|
| 페이지 응답 시간 (캐시 히트) | ~30초 (1시간마다) | ~10ms (즉시) |
| OpenAI API 호출 빈도 | 1회/시간/유저 | 독서 기록 변경 시만 |
| 프로세스 재시작 후 | 캐시 소멸, 첫 요청 지연 | DB에서 즉시 로드 |
| 캐시 정확도 | 불완전 (일부 변경 누락) | 모든 변경 이벤트 커버 |

---

## 13. 구현 순서 요약

```
1. user_preference_profiles 모델 정의
2. profile_cache.py 서비스 구현 (mark_dirty, get_or_create, update)
3. user_books.py API에 mark_dirty 추가 (4개 트리거)
4. imports.py에 mark_dirty 추가
5. recommend.py 캐시 로직 DB로 전환
6. recommendations.py 신규 엔드포인트 추가
7. 스키마 업데이트
8. 통합 테스트
```

> **CONFIRM 필요**: 위 설계로 진행할까요? 특히 질문 기반 추천(`/ask` 엔드포인트)의 응답 포맷이나
> `preference_vector` 저장 방식(JSONB vs PostgreSQL ARRAY)에 대한 의견이 있으면 알려주세요.
