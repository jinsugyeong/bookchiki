# 📚 독서 기록 + AI 책 추천 서비스 — Claude Code 플랜

## 프로젝트 개요

사용자의 독서 기록과 평점을 기반으로 AI가 책을 추천해주는 개인화 독서 서비스.
북스타그램 운영자를 위한 인스타 카드 이미지 생성은 부가 기능으로 제공한다.

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프론트엔드 | Next.js (App Router) + Tailwind CSS |
| 백엔드 | FastAPI (Python) |
| 메인 DB | PostgreSQL (유저, 책, 이미지 메타데이터) |
| 검색/벡터 | OpenSearch (지식 RAG + 벡터 인덱싱) |
| AI | OpenAI API (GPT-4o-mini, text-embedding-3-small) |
| 이미지 저장 | AWS S3 |
| 배포 | AWS EC2 (백엔드) + Vercel (프론트) + AWS RDS (PostgreSQL) |
| 인증 | Google OAuth 2.0 |


---

## 핵심 기능

### 1. 📖 내 독서 기록 (메인 기능)
- 읽은 책 등록 (책 제목 검색 → 알라딘 API 또는 Google Books API로 자동 정보 수집)
- 별점 (1~5점) + 독서 메모 / 한줄평 작성
- 읽는 중 / 읽고 싶어요 / 다 읽음 상태 관리
- 독서 통계 대시보드 (월별 독서량, 장르 분포, 평균 별점 등)
- 외부 앱 (북적북적 등) CSV/JSON 임포트로 기존 기록 마이그레이션

### 2. 🎯 AI 책 추천 (메인 기능)
- 내 독서 기록 + 별점 기반 개인화 추천
  - 별점 가중치 반영: 높은 별점 책일수록 취향 벡터에 더 큰 가중치 부여
  - OpenSearch KNN 벡터 검색으로 유사 도서 탐색
- "이 책을 좋아하면 이런 책도 좋아할 거예요" + AI 추천 이유 코멘트 제공
- 자연어 책 검색: "자기계발인데 너무 뻔하지 않은 책" 같은 RAG 기반 시맨틱 검색

### 3. 🖼️ 인스타 카드 이미지 생성 (부가 기능)
- 책 제목 입력 → Agent가 책 핵심 문구 / 명언 추출
- 인스타 카드 스타일 이미지 생성 (1:1, 4:5)
- 이미지 스타일 프리셋 선택 (미니멀, 감성, 모던 등)
- 생성된 이미지 텍스트 편집 (Canvas 에디터로 문구 / 폰트 / 색상 수정)
- 버전 관리 (원본 보존 + 수정본 저장) 후 다운로드

---

## 데이터 모델 (PostgreSQL)

```
users
- id, email, name, profile_image, created_at

books
- id, title, author, isbn, description, cover_image_url, genre, published_at

generated_images
- id, user_id, book_id, image_url (S3), style, prompt_used, created_at

image_versions (텍스트 편집 버전 관리)
- id, generated_image_id, version_number, image_url (S3), text_elements (JSON), created_at

user_books (읽은 책 / 찜한 책)
- id, user_id, book_id, status (read / wishlist), rating (1~5), memo, source (manual / import), created_at

book_imports (외부 앱 임포트 이력)
- id, user_id, source_app (bookcheok / csv 등), imported_count, created_at

recommendations
- id, user_id, book_id, score, reason, created_at
```

---

## 시스템 아키텍처

```
[Next.js 프론트]
      ↓ REST API
[FastAPI 백엔드]
   ↙        ↘
[PostgreSQL]  [OpenSearch]
              (벡터 + 키워드 인덱스)
      ↓
[AI Agent (Claude API)]
   ├─ 책 정보 수집 Tool
   ├─ RAG 검색 Tool (OpenSearch)
   ├─ 이미지 프롬프트 생성 Tool
   └─ 이미지 생성 Tool (DALL-E 3)
      ↓
   [AWS S3]
```

---

## 개발 단계별 플랜

### Phase 1 — 기반 인프라 ✅ 완료
- [x] FastAPI 프로젝트 세팅 (디렉토리 구조, 환경변수)
- [x] PostgreSQL 연결 + SQLAlchemy ORM 모델 정의
- [x] Docker Compose 세팅 (백엔드 + PostgreSQL + OpenSearch)

### Phase 2 — 독서 기록 ✅ 완료
- [x] 알라딘 API 연동 (책 검색 + 정보 수집 + 선택 저장)
- [x] 별점 + 메모 + 하이라이트 입력 API
- [x] 북적북적 CSV 임포트 파싱 로직 (중복 감지 포함)
- [x] 독서 통계 집계 API (월별 독서량, 장르 분포, 평균 별점)

### Phase 3 — OpenSearch + AI 추천 (초기 구현 ✅, 재설계로 대체)
- [x] 별점 가중치 반영 취향 벡터 계산
- [x] 추천 캐싱 (`is_dirty` 이벤트 기반)
- ~~[x] GPT-4o-mini로 책 후보 생성~~ → Phase 4에서 OpenSearch 검색으로 대체
- ~~[x] 알라딘 API 실존 검증 (퍼지 매칭)~~ → 제거 (books 인덱스가 실존 책만 포함)
- ~~[x] 취향 벡터 cosine similarity 재랭킹~~ → OpenSearch k-NN으로 대체

### Phase 3.5 — 초기 도서 데이터 시딩 ✅ 완료

> **목표:** 외부 도서 데이터를 books DB에 대량 시딩하여 시스템 1 추천 풀 확장

#### 추천 시스템 아키텍처 결정
- **시스템 1 (취향 기반):** 외부 데이터에서 **책 제목만** 추출 → 알라딘 검증 → books 풀 등록 → 취향 벡터 재랭킹 파이프라인 활용
- **시스템 2 (자연어 질문 기반):**
  - **구현 완료** (`/recommendations/ask`): 저장된 취향 프로필 + 사용자 질문 → `rag_knowledge` 인덱스 하이브리드 검색 → LLM 맞춤 추천
- **파서 공용:** 외부 데이터를 책 제목 (시스템 1용) + 청크 텍스트 (시스템 2용) 모두 추출

#### 데이터 소스 (`output/` 디렉토리)
| 파일 | 목적 | 청크 수 |
|---|---|---|
| `book_reviews.json` | 책 제목 추출 + 리뷰 청크 임베딩 | 2,456 |
| `thread_review.json` | 책 제목 추출 + 후기 청크 임베딩 | 641 |
| `monthly_closing_best.md` | 책 제목 추출 + 월별 랭킹 청크 임베딩 | 65 |
| `recommend.md` | 카테고리별 추천 청크 임베딩 | 521 |
| **합계** | | **3,683** |

#### 구현 태스크 ✅ 완료
- [x] `rag_pipeline/parsers/` — 4개 소스별 파서 (base, recommend, book_reviews, monthly_closing, thread_reviews)
- [x] `backend/app/services/data_seeder.py` — 파서에서 책 제목 추출 + 알라딘 검증 + books DB 시딩
- [x] `POST /admin/seed-books` — 관리자 시딩 엔드포인트
- [x] `rag_pipeline/pipeline.py` — 전체 청크 임베딩 + `rag_knowledge` 인덱스 적재
- [x] `backend/app/services/rag.py` — `embed_text()` + `search_knowledge()` (하이브리드 검색)
- [x] `opensearch/index.py` — `rag_knowledge` 인덱스 매핑 + `ensure_knowledge_index()`
- [x] `POST /recommendations/ask` — 질문 기반 맞춤 추천 엔드포인트 (RAG + LLM)
- [x] `GET /recommendations/profile` — 취향 프로필 조회 엔드포인트
- [x] `scripts/backup_rag_knowledge.py` — rag_knowledge 인덱스 JSON 덤프 백업
- [x] `scripts/restore_rag_knowledge.py` — 백업에서 재임베딩 없이 복원

### Phase 4 — 추천 시스템 재설계 🚧 진행 중

> **목표:** LLM 후보 생성 + 알라딘 검증 파이프라인 → OpenSearch 하이브리드 검색 기반으로 전환.
> DB 캐시 (`is_dirty` 이벤트 기반) + 유저 메모 임베딩 반영 + 앙상블(CF) 준비.

#### 설계 문서
- [docs/recommendation-profile-cache-design.md](./recommendation-profile-cache-design.md) — 캐시 아키텍처 설계

#### 완료된 작업 ✅
- [x] `user_preference_profiles` 모델 정의
- [x] `profile_cache.py` 서비스 구현 (mark_dirty, get_or_create, update, is_recommendation_fresh)
- [x] `user_books.py` API에 dirty 마킹 추가 (4개 트리거)
- [x] `imports.py`에 CSV 임포트 후 dirty 마킹 추가
- [x] `recommendations.py` 신규 엔드포인트 (`/ask`, `/profile`, `/refresh`)
- [x] 스키마 업데이트 (AskRequest/Response, ProfileResponse, PipelineStatusResponse, SeedStatusResponse)

#### 구현 태스크 (Phase 4.1 — OpenSearch 인프라) ✅ 완료
- [x] 1. `opensearch/index.py` — `books`, `user_books` 인덱스 매핑 추가
- [x] 2. `services/book_indexer.py` (신규) — books DB → `books` 인덱스 임베딩/upsert
- [x] 3. `services/user_book_indexer.py` (신규) — user_books 평점/메모 → `user_books` 인덱스 임베딩/upsert (`book_embedding` + `memo_embedding` 통합)
- [x] 4. `main.py` — `ensure_books_index()`, `ensure_user_books_index()` 시작 시 호출
- [x] `POST /admin/index-books`, `POST /admin/index-user-books` 엔드포인트 추가

#### 구현 태스크 (Phase 4.2 — 검색/추천 파이프라인) ✅ 완료
- [x] 5. `services/book_search.py` (신규) — `books` 인덱스 하이브리드 검색 (BM25 + k-NN)
  - `search_books_hybrid(preference_vector, genre_keywords, exclude_book_ids, k)` — 하이브리드 검색 (폴백: k-NN 단독)
  - `search_books_cold_start(k)` — 취향 벡터 없을 때 폴백 검색
- [x] 6. `services/recommend.py` 전면 재작성
  - LLM 후보 생성 / 알라딘 검증 / 인메모리 재랭킹 / 인메모리 캐시 제거
  - 취향 벡터 = α × 평점가중_책임베딩 + (1-α) × 메모평균_임베딩 (α=0.6)
  - user_books 인덱스 단일 쿼리로 취향 벡터 계산 (OpenSearch)
  - books 인덱스 하이브리드 검색으로 후보 추출
  - is_dirty DB 캐시로 캐시 히트 시 recommendations 테이블 직접 조회
  - LLM은 추천 이유 생성만 (GPT-4o-mini)
- [x] 7. `api/recommendations.py` — `/ask` 엔드포인트에서 알라딘 검증 제거
- [x] 8. `api/user_books.py` — 평점/메모 변경 시 `user_books` 인덱스 실시간 갱신
  - add: `index_user_book()` 호출
  - update: `index_user_book()` 호출
  - delete: `delete_user_book()` 호출
- [x] `opensearch/index.py` — `ensure_books_index()`에 `_ensure_hybrid_pipeline()` 추가
- [x] `profile_cache.py` — `update_profile()`, `is_recommendation_fresh()` 함수 추가

#### 구현 태스크 (Phase 4.3 — Synthetic 행렬 + ALS 앙상블 CF) ✅ 완료

> **Netflix/Spotify 방식:** 오프라인 배치 파이프라인에서 학습 → 결과물(추천 점수 보정)만 활용. 프로덕션 DB에 synthetic 흔적 없음.

**Synthetic 행렬 구성 전략:**
- `thread_review.json`: 41개 `post_num` → synthetic_user (각 평균 15.6권). 같은 게시글 = 비슷한 취향의 독자 그룹 → implicit CF 신호
- `book_reviews.json`: 책별 리뷰 수 → popularity confidence 가중치 (선택적)
- `recommend.md`, `monthly_closing_best.md`: 맥락 태그 / popularity → cold start 보완 (추후 확장)

**오프라인 배치 파이프라인 (`scripts/train_cf.py`):**
```
RAG 데이터(thread_review.json) + DB user_books
    ↓ 책 제목 → book_id 매핑 (books 테이블)
    ↓ Synthetic(41명) + Real 유저 → scipy.sparse user×item 행렬
    ↓ implicit ALS 학습 (factors=64, iterations=20, regularization=0.1)
    ↓ backend/models/cf_model.npz + cf_mapping.json 저장

실행: docker compose exec -w /project backend python scripts/train_cf.py
옵션: --factors 64 --iterations 20 --regularization 0.1
```

**프로덕션 CF 점수 조회 (`backend/app/services/cf_scorer.py`):**
- 모델 파일 로드 (싱글톤, 없으면 graceful degradation)
- `get_scores(user_id, book_ids)` → {book_id: 0.0~1.0} min-max 정규화 점수
- 모델 없거나 유저 미매핑: 빈 dict 반환 (OpenSearch만 사용)

**앙상블 스코어링 (`recommend.py` 업데이트):**
- `final_score = α × OpenSearch점수 + (1-α) × CF점수`
- α 동적 계산: 서재 < 10권 → α=0.9, 10-29권 → α=0.7, ≥ 30권 → α=0.5
- CF 모델 없으면 graceful degradation (α=1.0, OpenSearch만)

**모델 파일 관리:**
- `backend/models/cf_model.npz` — NumPy binary (user_factors, item_factors)
- `backend/models/cf_mapping.json` — 유저/책 인덱스 매핑 + 메타데이터
- `.gitignore`에 추가 (Git 미관리, 로컬/CI 생성)
- 모델 학습 후 `docker compose restart backend` 필요 (싱글톤 재로드)

**구현 태스크:**
- [x] 9. `requirements.txt`에 `implicit`, `scipy` 추가
- [x] 10. `scripts/train_cf.py` — Synthetic 행렬 빌드 + ALS 학습 + 모델 저장
- [x] 11. `backend/app/services/cf_scorer.py` — CF 점수 조회 서비스 (싱글톤)
- [x] 12. `recommend.py` — CF 앙상블 스코어링 추가 (`_compute_ensemble_alpha()`, `_apply_cf_ensemble()`)
- [x] 13. Alembic 마이그레이션 파일 생성 (390a85298b3d에 user_preference_profiles 포함됨)
- [x] 14. 단위 테스트 작성 (test_cf_scorer.py, test_recommend_ensemble.py, test_train_cf.py)


### Phase 5 — 프론트엔드 ✅ 완료

**기술 스택:** Next.js 15 + Tailwind v4 + TanStack Query v5 + Lucide React
**디자인:** Soft Modern (크림 베이지 배경 `#FFFDF9`, 주력 텍스트 `#1C1917`, 앰버 액센트 `#E8A045`)
**폰트:** Pretendard (CDN, 한국어 sans-serif)
**배포:** `frontend/Dockerfile` + Docker Compose (포트 3000)

#### 완료된 페이지/기능
- [x] **홈 (`/`)**: 랜딩 페이지 (HeroSection, FeaturesSection, DashboardSection, LibrarySection, AISection, MypageSection, CTASection)
- [x] **책 검색 (`/library/search`)**: 알라딘 API 검색 + 서재 추가 모달 + 추가 취소 기능
- [x] **내 서재 (`/library`)**: 책 목록, 상태별 필터(읽는중/완료/찜), 책 상세/편집 모달, 평점/메모/상태 수정
- [x] **추천 (`/recommendations`)**: 시스템1(취향 기반 `GET /recommendations`) + 시스템2(질문 기반 `POST /recommendations/ask`) 탭
- [x] **마이페이지 (`/mypage`)**: 프로필, 통계, CSV 임포트, 계정 관리
- [x] **로그인 (`/login`)**: Google OAuth

#### 구현 세부 사항
- [x] 백엔드는 Docker (`docker compose up`), 프론트엔드는 별도 실행 (`npm run dev`)
- [x] 파비콘 동적 생성 (`app/icon.tsx`, 헤더 로고와 동일)
- [x] `.gitignore` 통합 (frontend/.gitignore → 루트로 병합)
- [x] 환경 변수 설정 (`NEXT_PUBLIC_API_URL=http://localhost:8000`)
- [x] API 통합 (TanStack Query v5로 자동 캐싱/리페칭)

### Phase 6 — 북스타그램 이미지 생성 ✅ 완료

#### 이미지 생성 전략 (DALL-E 3)
- 유저당 일일 최대 3회 제한 (DB 트래킹)
- 책 정보(제목, 저자, 장르, 설명) 기반 atmospheric 배경 이미지 생성
- 텍스트 없는 순수 배경 스타일로 생성하여 overlay 편집 용이성 확보

#### 구현 태스크 ✅ 완료
- [x] `backend/app/api/images.py` — DALL-E 3 연동 배경 이미지 생성 API
- [x] `GenerateBackgroundRequest/Response` 스키마 정의
- [x] `DAILY_LIMIT=3` 정책 및 UTC 기준 일일 카운트 로직 (`_count_today_generations`)
- [x] 프론트엔드: Canvas 기반 텍스트 편집 에디터 및 이미지 다운로드 기능 (`frontend/hooks/useImageExport.ts` 등)
- [x] `GeneratedImage` 모델로 생성 이력 관리
- [x] `GET /images/daily-remaining` — 남은 횟수 조회 API
- [x] `POST /images/generate-background` — 배경 생성 API (DALL-E 3)
- [x] 비로그인 랜딩 페이지 홍보 섹션 추가 및 레이아웃 최적화 (3+2 구도)

---

## 비용 관리 전략

- 이미지 생성은 유저당 하루 3회 제한 (DALL-E 3 비용 관리)
- OpenSearch는 개발 중 로컬 Docker로 대체, 배포 시에만 AWS 사용
- OpenAI API 호출 결과(추천 결과)는 DB 캐싱 레이어 활용
- S3 이미지(수정본 등)는 30일 후 자동 삭제 정책 예정 (비용 절감)

---

## 폴더 구조

```
project-root/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI 라우터
│   │   ├── models/       # SQLAlchemy 모델
│   │   ├── services/     # 비즈니스 로직
│   │   │   ├── aladin.py        # 알라딘 API 클라이언트
│   │   │   ├── rag.py           # RAG 파이프라인 (OpenAI 임베딩)
│   │   │   ├── recommend.py     # 추천 시스템 (OpenSearch 하이브리드 + CF 앙상블)
│   │   │   ├── cf_scorer.py     # CF 협업 필터링 점수 조회
│   │   │   ├── book_search.py   # OpenSearch 검색
│   │   │   ├── book_indexer.py  # books 인덱싱
│   │   │   ├── user_book_indexer.py # user_books 인덱싱
│   │   │   ├── profile_cache.py # 취향 프로필 캐시
│   │   │   ├── book_import.py   # CSV 임포트
│   │   │   └── data_seeder.py   # 도서 데이터 시딩
│   │   ├── opensearch/   # OpenSearch 연동
│   │   └── core/         # 설정, 인증
│   ├── models/           # CF 모델 저장소 (cf_model.npz, cf_mapping.json)
│   ├── alembic/          # DB 마이그레이션
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/             # Next.js 15 앱 (Phase 5 완료)
│   ├── app/
│   │   ├── page.tsx      # 홈 페이지
│   │   ├── layout.tsx    # 메인 레이아웃
│   │   ├── (auth)/
│   │   │   └── login/    # Google OAuth 로그인
│   │   ├── library/      # 내 서재 + 책 검색
│   │   ├── recommendations/  # 추천 (시스템1, 시스템2)
│   │   └── mypage/       # 마이페이지
│   ├── components/       # UI 컴포넌트
│   ├── hooks/           # React 훅
│   ├── services/        # API 클라이언트
│   ├── tailwind.config.ts
│   └── package.json
├── scripts/
│   ├── train_cf.py      # CF 모델 학습
│   └── ...
├── .dockerignore
├── docker-compose.yml   # 로컬 개발용 (백엔드 + PostgreSQL + OpenSearch + 프론트엔드)
├── .gitignore
├── .env.example
└── docs/
    ├── plan.md
    └── ...
```

---

## Claude Code 시작 프롬프트

아래를 Claude Code에 그대로 붙여넣어서 시작하세요.

```
독서 기록과 별점 기반 AI 책 추천 웹 서비스를 만들려고 해.
북스타그램 운영자를 위한 인스타 카드 이미지 생성은 부가 기능이야.

기술 스택:
- 백엔드: FastAPI + PostgreSQL + OpenSearch
- 프론트엔드: Next.js + Tailwind CSS
- AI: Claude API (RAG + Agent) + DALL-E 3 (이미지 생성은 부가 기능)
- 인프라: AWS EC2, S3, RDS

핵심 기능 (우선순위 순):
1. [메인] 독서 기록 관리: 읽은 책 등록, 별점(1~5) + 메모 작성, 상태 관리(읽는 중/다 읽음/읽고 싶어요), 독서 통계 대시보드
2. [메인] AI 책 추천: 별점 가중치 반영 + OpenSearch KNN 벡터 검색 기반 개인화 추천, 자연어 책 검색
3. [부가] 인스타 카드 이미지 생성 + 텍스트 편집 (Canvas 에디터)
4. 북적북적 등 외부 앱 CSV/JSON 데이터 임포트

먼저 backend/ 폴더를 만들고 FastAPI 프로젝트 기본 구조를 세팅해줘.
PostgreSQL 연결, 기본 모델 (users, books, generated_images, image_versions, user_books, book_imports, recommendations) 정의,
그리고 로컬 개발용 docker-compose.yml (PostgreSQL + OpenSearch 포함)까지 만들어줘.
```
