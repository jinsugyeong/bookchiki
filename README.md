# Bookchiki (북치기박치기)

사용자의 독서 기록과 평점을 기반으로 AI가 책을 추천해주는 개인화 독서 서비스.

- 📖 **독서 기록 관리** — 읽은 책 등록, 별점, 메모/하이라이트
- 🎯 **AI 책 추천** — 시스템1: 기록 기반 개인화 추천 / 시스템2: 취향 프로필 + 자연어 질문 기반 맞춤 추천
- 📊 **독서 통계** — 월별 독서량, 장르 분포, 평균 평점
- 📥 **데이터 임포트** — 북적북적 등 외부 앱 CSV 가져오기
- 🖼 **북스타그램 이미지 생성** — 하이라이트 기반 카드 이미지 자동 생성 (예정)

## 기술 스택

| 영역 | 기술 |
|------|------|
| 백엔드 | FastAPI (Python 3.12) |
| 메인 DB | PostgreSQL 16 |
| 검색/벡터 | OpenSearch 2.17 (하이브리드 BM25 + KNN) |
| AI/ML | OpenAI API (GPT-4o-mini, text-embedding-3-small) |
| 도서 데이터 | 알라딘 TTB API |
| 프론트엔드 | Next.js App Router (예정) |
| 배포 | AWS EC2 + RDS + OpenSearch / Vercel (프론트) |
| 인증 | Google OAuth 2.0 + JWT |

## 추천 시스템

### 시스템 1 — 기록 기반 개인화 추천

DB 영속 취향 프로필 (`user_preference_profiles`) + `is_dirty` 이벤트 기반 캐시로 즉시 응답.

```
GET /recommendations
        │
   is_dirty 확인
   ┌─────┴─────┐
false           true
   │               │
캐시 히트        파이프라인 실행
(~10ms)         ├─ GPT-4o-mini로 책 후보 생성 (limit × 2.5개)
                ├─ 알라딘 API 실존 검증 (퍼지 매칭 0.75, 동시 5개)
                ├─ 취향 벡터 cosine similarity 재랭킹
                ├─ 최종 N권만 DB + OpenSearch 저장
                ├─ user_preference_profiles 갱신 (is_dirty=false)
                └─ 추천 이유 생성 (GPT-4o-mini)
```

**Dirty 마킹 트리거:** 책 추가 / 평점·메모·상태 변경 / 책 삭제 / CSV 임포트

### 시스템 2 — 자연어 질문 기반 맞춤 추천

저장된 취향 프로필과 지식 베이스를 활용하여 자유 질문에 맞는 맞춤 추천을 제공.

```
POST /recommendations/ask  { "question": "감동적인 가족 이야기 추천해줘" }
        │
user_preference_profiles.profile_data 조회
        │
rag_knowledge 인덱스에서 관련 정보 하이브리드 검색 (BM25 + KNN)
        │
취향 프로필 + 질문 + 검색 결과 → LLM이 맞춤 추천 생성
        │
취향 프로필 기반 추천 + AI 설명 반환 (캐시 overwrite 없음)
```

## 빠른 시작

```bash
# 1. 환경 설정
cd backend && cp .env.example .env
# .env: OPENAI_API_KEY, ALADIN_API_KEY, JWT_SECRET_KEY 필수 입력

# 2. 실행 (백엔드 :8000 · PostgreSQL :5432 · OpenSearch :9200)
docker compose up

# 3. DB + 인덱스 초기화 (최초 1회 또는 리셋 시)
cd backend && python reset_db.py
```

- Swagger UI: http://localhost:8000/docs
- Health 체크: http://localhost:8000/health

**개발 모드 인증 우회:** `APP_ENV=development` 상태에서 Bearer 토큰 없이 요청하면 `dev@bookchiki.local` 사용자 자동 생성.

## 주요 API

| 엔드포인트 | 설명 |
|-----------|------|
| `POST /books/search` | 알라딘 도서 검색 |
| `GET /my-books` | 내 서재 조회 |
| `POST /my-books/{book_id}` | 평점/상태 업데이트 |
| `GET /recommendations` | 개인화 추천 (캐시 히트 시 ~10ms) |
| `POST /recommendations/ask` | 질문 기반 맞춤 추천 |
| `GET /recommendations/profile` | 취향 프로필 조회 |
| `POST /recommendations/refresh` | 강제 추천 재생성 |
| `POST /imports/csv` | CSV 임포트 |
| `POST /admin/seed-community-books` | 커뮤니티 데이터 시딩 (관리자) |

## 프로젝트 구조

```
bookchiki/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI 라우터
│   │   ├── models/         # SQLAlchemy ORM
│   │   ├── services/
│   │   │   ├── aladin.py           # 알라딘 API 클라이언트
│   │   │   ├── book_import.py      # CSV 파싱
│   │   │   ├── rag.py              # 임베딩 + 하이브리드 검색
│   │   │   ├── recommend.py        # 추천 파이프라인 (기록 기반)
│   │   │   ├── profile_cache.py    # 취향 프로필 캐시 관리 (신규, 재설계 중)
│   │   │   └── rag_pipeline/       # 커뮤니티 데이터 파서
│   │   │       └── parsers/        # recommend / book_reviews / monthly_closing / thread_reviews
│   │   ├── opensearch/     # 인덱스 매핑 관리
│   │   └── core/           # 설정, DB, 인증
│   └── .env.example
├── docker-compose.yml
├── docs/plan.md            # 개발 로드맵
└── CLAUDE.md               # Claude Code 작업 가이드
```


## 환경 변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `DATABASE_URL` | ✅ | `.env.example` 참고 |
| `OPENAI_API_KEY` | ✅ | GPT-4o-mini + 임베딩 |
| `ALADIN_API_KEY` | ✅ | 도서 검색/검증 |
| `JWT_SECRET_KEY` | ✅ | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `OPENSEARCH_HOST` | — | 기본값 `opensearch` (Docker) |
| `APP_ENV` | — | `development` (인증 우회) / `production` |
| `GOOGLE_CLIENT_ID/SECRET` | — | OAuth (프로덕션만 필수) |
| `FRONTEND_URL` | — | CORS 허용 URL |

## 주의사항

- **DB/인덱스 리셋** — 모든 데이터 삭제. 반드시 확인 후 진행
- **API 키** — `.env` 파일을 절대 커밋하지 말 것
- **개발 모드** — `APP_ENV=development`일 때만 인증 우회 활성화
