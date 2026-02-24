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
- [x] `backend/app/services/community_seeder.py` — 파서에서 책 제목 추출 + 알라딘 검증 + books DB 시딩
- [x] `POST /admin/seed-community-books` — 관리자 시딩 엔드포인트
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

#### 구현 태스크 (Phase 4.2 — 검색/추천 파이프라인)
- [ ] 5. `services/book_search.py` (신규) — `books` 인덱스 하이브리드 검색 (BM25 + k-NN)
- [ ] 6. `services/recommend.py` 전면 재작성
  - LLM 후보 생성 / 알라딘 검증 / 인메모리 재랭킹 제거
  - 취향 벡터 = 평점 가중 책 임베딩 + 메모 임베딩 합산
  - OpenSearch `books` 인덱스 하이브리드 검색으로 후보 추출
  - LLM은 추천 이유 생성만
- [ ] 7. `api/recommendations.py` — `/admin/index-books`, `/admin/index-user-books` 엔드포인트 추가
- [ ] 8. `api/user_books.py` — 평점/메모 변경 시 `user_books` 인덱스 실시간 갱신

#### 구현 태스크 (Phase 4.3 — 앙상블 CF, 데이터 충분 후)
- [ ] 9. CF 모델 학습 (ALS 또는 LightFM)
  - 학습 데이터: `user_books` 평점 + 메모 임베딩 + 읽기 상태
- [ ] 10. 앙상블 스코어링: `α × OpenSearch점수 + (1-α) × CF점수`
  - α 동적 조절: 서재 책 수 < 10 → α=0.9, ≥ 30 → α=0.5
- [ ] 11. Alembic 마이그레이션 파일 생성
- [ ] 12. 통합 테스트 작성


### Phase 5 — 프론트엔드 ⏳ 예정
- [ ] 메인 페이지 (서비스 소개 + 책 추천 시스템 1 + 독서 통계 대시보드 + 책 추천 시스템2(모달))
- [ ] 내 서재 페이지 (독서 기록 목록, 서재 책 검색, 정렬, 별점/메모 입력)
- [ ] CSV 임포트 페이지
- [ ] 이미지 생성 페이지 (책 선택 → 스타일 → 생성 → 텍스트 편집 → 다운로드) **나중에
- [ ] 마이페이지 (독서 통계, 이미지 히스토리, 내 정보 관리)

### Phase 6 — 북스타그램 이미지 생성 ⏳ 예정

#### 이미지 생성 API 후보 (미결정)
| 옵션 | 비용 | 비고 |
|------|------|------|
| **Pollinations.ai** | 무료 | API 키 불필요, GET 요청으로 즉시 생성, 상업 이용 가능 → **1순위** |
| Hugging Face Inference API | 무료 티어 | FLUX.1-schnell, rate limit 있음 |
| Replicate | ~$0.002/장 | SDXL·FLUX 선택 가능, 종량제 |
| DALL-E 3 | $0.04/장 | 품질 최상, 비용 높음 |

#### 구현 태스크
- [ ] 이미지 생성 API 최종 선택 및 연동
- [ ] `extract_book_quote` — 하이라이트/메모에서 핵심 문구 추출
- [ ] `generate_image_prompt` — 카드 이미지 프롬프트 생성
- [ ] `create_image` — 이미지 생성 + 저장 (S3 또는 로컬)
- [ ] Canvas 기반 텍스트 편집 에디터 (문구 / 폰트 / 색상)
- [ ] `image_versions` 테이블로 버전 관리

---

## 비용 관리 전략

- 이미지 생성은 하루 N회 제한 로직 추가 (DB에 daily_count 트래킹)
- OpenSearch는 개발 중 로컬 Docker로 대체, 배포 시에만 AWS 사용
- Claude API 호출에 캐싱 레이어 추가 (같은 책 재요청 시 재사용)
- S3 이미지는 30일 후 자동 삭제 정책 (비용 절감)

---

## 폴더 구조

```
project-root/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI 라우터
│   │   ├── models/       # SQLAlchemy 모델
│   │   ├── services/     # 비즈니스 로직
│   │   │   ├── agent.py       # AI Agent
│   │   │   ├── rag.py         # RAG 파이프라인
│   │   │   ├── recommend.py   # 추천 시스템
│   │   │   ├── image_gen.py   # 이미지 생성
│   │   │   ├── image_editor.py # 이미지 텍스트 편집 + 버전 관리
│   │   │   └── book_import.py  # 외부 앱 데이터 임포트
│   │   ├── opensearch/   # OpenSearch 연동
│   │   └── core/         # 설정, 인증
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/
│   ├── components/
│   └── ...
└── docker-compose.yml    # 로컬 개발용
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
