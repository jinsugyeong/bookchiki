# 개발 가이드

마지막 업데이트: 2026-03-03 (Phase 5 프론트엔드 완료 + Refresh Token 구현)

이 문서는 Bookchiki 프로젝트의 개발 환경 세팅, 실행 방법, 그리고 테스트 방법을 설명합니다.

---

## 개발 환경 요구사항

- **Python:** 3.10 이상
- **Node.js:** 20 이상 (프론트엔드용)
- **PostgreSQL:** 16 (Docker 또는 로컬 설치)
- **OpenSearch:** 2.0 이상 (Docker)
- **Docker & Docker Compose:** (권장) 로컬 서비스 실행용

---

## 초기 세팅

### 1. 저장소 클론

```bash
git clone https://github.com/your-org/bookchiki.git
cd bookchiki
```

### 2. 환경변수 설정

```bash
cp backend/.env.example backend/.env
```

`.env` 파일을 열고 다음 항목을 설정하세요:

- `DATABASE_URL` — PostgreSQL 연결 주소
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — Google OAuth 인증
- `JWT_SECRET_KEY` — JWT 토큰 서명 키 (개발 환경은 아무 값이나 가능)
- `ALADIN_API_KEY` — 알라딘 TTB API 키
- `OPENAI_API_KEY` — OpenAI API 키 (임베딩 및 추천 이유 생성용)
- `APP_ENV` — `development` 또는 `production`

자세한 환경변수 설명은 [ENV.md](./docs/ENV.md) 참고.

### 3. Python 가상환경 구성

**옵션 A: Docker Compose 사용 (권장)**

Docker가 설치되어 있다면:

```bash
docker compose up
```

이 명령어로 백엔드, PostgreSQL, OpenSearch가 모두 시작됩니다.

**옵션 B: 로컬 실행 (Docker 없이)**

```bash
cd backend

# 가상환경 생성
python -m venv venv

# 활성화
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

PostgreSQL과 OpenSearch는 별도로 설치 또는 Docker로 실행해야 합니다.

---

## 서비스 실행

### Docker Compose로 전체 실행

```bash
docker compose up
```

상태 확인:
- **프론트엔드:** http://localhost:3000 (Next.js + Tailwind v4)
- **백엔드:** http://localhost:8000 (API 문서: http://localhost:8000/docs)
- **PostgreSQL:** localhost:5432
- **OpenSearch:** http://localhost:9200

### 프론트엔드만 로컬 개발 서버 실행

```bash
cd frontend
npm install  # 처음 1회
npm run dev  # 개발 서버 시작 → http://localhost:3000
```

**주의:** 백엔드가 http://localhost:8000에서 실행 중이어야 합니다. `frontend/.env.local`에서 `NEXT_PUBLIC_API_URL` 확인.

**프론트엔드 페이지:**
- `/` — 홈 (비회원 랜딩 + 회원 홈 페이지 + 통계)
- `/login` — Google OAuth 로그인 페이지
- `/auth/callback` — OAuth 콜백 (자동 리다이렉트)
- `/library` — 내 서재 (책 목록 + 통계)
- `/library/search` — 도서 검색 (알라딘 API 검색)
- `/recommendations` — 추천 탭 (시스템 1: 기록 기반 + 시스템 2: 질문 기반)
- `/mypage` — 마이페이지 (프로필 정보)

### 로컬에서 백엔드만 실행

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`--reload` 플래그는 파일 변경 시 자동으로 서버를 재시작합니다.

### 서비스 중지

```bash
docker compose down
```

모든 데이터를 삭제하려면:

```bash
docker compose down -v
```

---

## 데이터베이스 관리

### 초기화 (전체 삭제 후 재생성)

```bash
cd backend
python reset_db.py
```

이 스크립트는:
1. PostgreSQL의 모든 테이블 삭제
2. OpenSearch의 `books` 인덱스 삭제
3. 새 테이블과 인덱스 재생성

### 마이그레이션 (Alembic)

테이블 구조 변경 후:

```bash
cd backend

# 마이그레이션 파일 생성
alembic revision --autogenerate -m "설명"

# 마이그레이션 적용
alembic upgrade head
```

**주의:** 현재 이 프로젝트는 Alembic 마이그레이션 파일이 없습니다. 앱 시작 시 `Base.metadata.create_all`로 테이블을 자동 생성합니다.

---

## API 문서

백엔드가 실행 중일 때:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

API 엔드포인트 상세 목록은 [API.md](./docs/API.md) 참고.

---

## 테스트

현재 백엔드 테스트 코드는 일부 작성되어 있습니다. (`backend/tests/`)

**테스트 실행:**
```bash
docker compose exec backend pytest tests/ -v
```

**테스트 작성 기준:**
- 최소 80% 코드 커버리지 목표
- Unit, Integration, E2E 테스트 포함
- TDD(테스트 주도 개발) 권장

---

## 인증 및 Refresh Token

모든 환경(개발/프로덕션)에서 **실제 Google OAuth + JWT 인증**을 사용합니다.

**토큰 관리:**
- **Access Token:** 기본 만료 60분 (환경변수로 조정 가능)
- **Refresh Token:** 기본 만료 7일 (환경변수로 조정 가능)
- **Refresh Token 저장:** PostgreSQL `refresh_tokens` 테이블
- **로그아웃:** Refresh Token 자동 폐기

**개발 중 Google OAuth 없이 테스트하려면:**
`.env`에 다음을 설정:
```bash
GOOGLE_CLIENT_ID=dummy
GOOGLE_CLIENT_SECRET=dummy
```

API 문서(Swagger UI)에서 "Authorize" 버튼으로 토큰을 직접 입력하거나, 프론트엔드 로그인 화면에서 Google 계정으로 로그인하세요.

---

## 주요 커맨드 정리

| 목적 | 커맨드 |
|------|--------|
| 전체 서비스 시작 (Docker) | `docker compose up` |
| 서비스 중지 | `docker compose down` |
| 데이터 전체 초기화 | `cd backend && python reset_db.py` |
| 백엔드 로컬 실행 | `cd backend && uvicorn app.main:app --reload` |
| 프론트엔드 개발 서버 | `cd frontend && npm run dev` |
| API 문서 조회 | http://localhost:8000/docs |
| 마이그레이션 생성 | `cd backend && alembic revision --autogenerate -m "..."` |
| 마이그레이션 적용 | `cd backend && alembic upgrade head` |
| CF 모델 학습 | `docker compose exec -w /project backend python scripts/train_cf.py` |
| 단위 테스트 | `docker compose exec backend pytest tests/ -v` |

---

## 폴더 구조

```
bookchiki/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI 라우터 (auth, books, user_books, recommendations, etc.)
│   │   ├── models/           # SQLAlchemy ORM 모델
│   │   ├── schemas/          # Pydantic 요청/응답 스키마
│   │   ├── services/         # 비즈니스 로직 (recommend, rag, aladin, cf_scorer, book_indexer, etc.)
│   │   ├── opensearch/       # OpenSearch 연동
│   │   ├── core/
│   │   │   ├── config.py     # 환경변수 로드
│   │   │   ├── database.py   # DB 연결
│   │   │   └── security.py   # 인증/JWT
│   │   └── main.py           # FastAPI 앱 진입점
│   ├── models/               # CF 모델 저장소 (cf_model.npz, cf_mapping.json)
│   ├── alembic/              # DB 마이그레이션
│   ├── requirements.txt      # Python 의존성
│   ├── Dockerfile
│   └── .env.example          # 환경변수 템플릿
│
├── frontend/                 # Phase 5: Next.js 15 + Tailwind v4
│   ├── app/
│   │   ├── page.tsx          # 홈 페이지
│   │   ├── layout.tsx        # 메인 레이아웃
│   │   ├── (auth)/           # 인증 라우트
│   │   │   └── login/
│   │   ├── library/          # 내 서재 + 책 검색
│   │   ├── recommendations/  # 추천 (시스템1, 시스템2)
│   │   └── mypage/           # 마이페이지
│   ├── components/           # UI 컴포넌트
│   ├── hooks/               # React 훅
│   ├── services/            # API 클라이언트
│   ├── Dockerfile
│   ├── tailwind.config.ts
│   ├── package.json
│   └── .env.local           # 환경변수 (NEXT_PUBLIC_API_URL)
│
├── scripts/                  # 헬퍼 스크립트
│   ├── train_cf.py          # CF 모델 학습
│   └── ...
│
├── docs/                     # 문서
│   ├── plan.md              # 개발 계획 (Phase 1~6)
│   ├── INDEX.md             # 문서 인덱스
│   ├── API.md               # API 엔드포인트
│   ├── ENV.md               # 환경변수
│   ├── CONTRIBUTING.md      # 개발 가이드
│   └── recommendation-profile-cache-design.md
│
├── docker-compose.yml       # 로컬 개발용 (백엔드 + 프론트엔드 + PostgreSQL + OpenSearch)
├── .dockerignore
├── .gitignore
├── .env.example
└── CLAUDE.md                # 프로젝트 개요 및 아키텍처

```

---

## 문제 해결

### PostgreSQL 연결 오류

```
sqlalchemy.exc.OperationalError: (asyncpg.exceptions.CannotConnectNowError)
```

**원인:** PostgreSQL이 실행 중이 아님.

**해결:**
- Docker: `docker compose up postgres`
- 로컬: PostgreSQL 서비스 재시작

### OpenSearch 연결 오류

```
elasticsearch.exceptions.TransportError: Connection refused
```

**원인:** OpenSearch가 실행 중이 아님.

**해결:**
- Docker: `docker compose up opensearch`

### JWT 토큰 관련 오류

**개발 환경에서 인증 우회:**

`.env`의 `APP_ENV`를 `development`로 설정하면 토큰 없이 API 호출 가능.

---

## 코딩 스타일 가이드

프로젝트 규칙:
- **코드:** 영어 (변수명, 함수명, 주석)
- **문서 / 로그:** 한국어
- **불변성:** 객체 변경 금지 (새 복사본 생성)
- **에러 처리:** 모든 레벨에서 명시적 처리

자세한 규칙은 프로젝트 루트의 `.claude/rules/common/coding-style.md` 참고.

---

## 다음 단계

1. [API.md](./API.md) — API 엔드포인트 상세 레퍼런스
2. [ENV.md](./ENV.md) — 환경변수 전체 목록
3. [CLAUDE.md](../CLAUDE.md) — 프로젝트 아키텍처 개요
