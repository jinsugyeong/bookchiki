# 환경변수 레퍼런스

마지막 업데이트: 2026-03-12

이 문서는 `backend/.env` 파일의 모든 환경변수를 설명합니다.

---

## 환경변수 로드 방식

`backend/app/core/config.py`에서 **pydantic-settings**를 사용하여 다음 우선순위로 로드합니다:

1. `.env` 파일 (있으면)
2. 시스템 환경변수
3. 기본값 (설정)

---

## 필수 환경변수

| 환경변수 | 설명 | 예시 | 형식 |
|---------|------|------|------|
| `DATABASE_URL` | PostgreSQL 비동기 연결 문자열 | `postgresql+asyncpg://user:pass@localhost:5432/bookchiki` | DSN |
| `GOOGLE_CLIENT_ID` | Google OAuth 클라이언트 ID | `123456789-abc.apps.googleusercontent.com` | String |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 클라이언트 비밀 | `GOCSPX-...` | String |
| `JWT_SECRET_KEY` | JWT 서명 키 (보안 필수) | 임의의 긴 문자열 | String |
| `ALADIN_API_KEY` | 알라딘 TTB API 키 | `ttbkor...` | String |
| `OPENAI_API_KEY` | OpenAI API 키 (임베딩 및 추천 이유 생성용) | `sk-...` | String |
| `TAVILY_API_KEY` | Tavily Search API 키 (질문 기반 실시간 도서 검색용) | `tvly-...` | String |
| `OPENSEARCH_INITIAL_ADMIN_PASSWORD` | docker-composer.yml에 들어가는 암호키(8자 이상, 영문 대소문자, 숫자, 특수문자 포함) | B0@kchiki | String |

---

## 선택사항 환경변수 (기본값 제공)

| 환경변수 | 설명 | 기본값 | 형식 |
|---------|------|--------|------|
| `JWT_ALGORITHM` | JWT 서명 알고리즘 | `HS256` | String |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 액세스 토큰 만료 시간 | `15` | Integer |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh Token 만료 시간 | `7` | Integer |
| `OPENSEARCH_HOST` | OpenSearch 호스트 | `opensearch` | String |
| `OPENSEARCH_PORT` | OpenSearch 포트 | `9200` | Integer |
| `OPENAI_EMBEDDING_MODEL` | OpenAI 임베딩 모델 | `text-embedding-3-small` | String |
| `APP_ENV` | 실행 환경 (`development` / `production`) | `development` | String |
| `FRONTEND_URL` | 프론트엔드 URL (OAuth 콜백용) | `http://localhost:3000` | String |
| `PG_HOST, PORT, ...` | 배포 환경에서 사용되는 PostgreSQL 정보들, postgres 백업 및 복구 스트립트에서 사용됨 | PG_HOST=your-rds-endpoint<BR>PG_PORT=5432<br>PG_USER=user<br>PG_DB=db<br>PG_PASSWORD=pass | |

---

## AWS S3 (이미지 저장용, 부가 기능)

| 환경변수 | 설명 | 예시 | 형식 |
|---------|------|------|------|
| `AWS_ACCESS_KEY_ID` | AWS 액세스 키 | `AKIAIOSFODNN7EXAMPLE` | String |
| `AWS_SECRET_ACCESS_KEY` | AWS 시크릿 키 | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` | String |
| `AWS_S3_BUCKET` | S3 버킷명 (이미지 저장) | `bookchiki-images` | String |
| `AWS_REGION` | AWS 리전 | `ap-northeast-2` | String |

---


## 환경별 설정 예시

### 로컬 개발 (Docker Compose)

```bash
# .env
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/bookchiki

GOOGLE_CLIENT_ID=your-prod-google-id
GOOGLE_CLIENT_SECRET=your-prod-google-secret

JWT_SECRET_KEY=<64자 이상 난수>

ALADIN_API_KEY=your-aladin-key

OPENAI_API_KEY=your-openai-key
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
TAVILY_API_KEY=your-tavily-key

AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_S3_BUCKET=bookchiki-images-prod
AWS_REGION=ap-northeast-2

OPENSEARCH_HOST=opensearch
OPENSEARCH_PORT=9200
OPENSEARCH_INITIAL_ADMIN_PASSWORD=your-opensearch-initial-admin-password

FRONTEND_URL=http://localhost:3000
```

### 프로덕션 배포

```bash
# .env (또는 환경변수로 주입)
DATABASE_URL=postgresql+asyncpg://user:pass@your-rds-endpoint:5432/bookchiki

PG_HOST=your-rds-endpoint
PG_PORT=5432
PG_USER=user
PG_DB=db
PG_PASSWORD=pass

GOOGLE_CLIENT_ID=your-prod-google-id
GOOGLE_CLIENT_SECRET=your-prod-google-secret

JWT_SECRET_KEY=<64자 이상 난수>

ALADIN_API_KEY=your-aladin-key

OPENAI_API_KEY=your-openai-key
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
TAVILY_API_KEY=your-tavily-key

AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_S3_BUCKET=bookchiki-images-prod
AWS_REGION=ap-northeast-2

OPENSEARCH_HOST=opensearch
OPENSEARCH_PORT=9200
OPENSEARCH_INITIAL_ADMIN_PASSWORD=your-opensearch-initial-admin-password

FRONTEND_URL=https://bookchiki.com
```

---

## 주의사항

### 보안

- **절대로 `.env` 파일을 Git에 커밋하지 마세요.** (`.gitignore`에 포함됨)
- 프로덕션 환경의 `JWT_SECRET_KEY`는 최소 64자 이상의 안전한 난수로 설정하세요.
- 모든 API 키는 환경변수로만 관리하세요.

### API 비용

- **OpenAI:** 임베딩 생성마다 비용 발생. 캐싱으로 중복 비용 방지.
- **Aladin:** 월별 요청 제한 있음. 

### OpenSearch 인덱스

`APP_ENV=development` / `production` 모두에서 앱 시작 시 `rag_knowledge` 인덱스 없으면 자동 생성됩니다.

---

## 환경변수 검증

백엔드 앱이 시작될 때 필수 환경변수를 자동으로 검증합니다.

오류 예시:

```
ValueError: DATABASE_URL is required
```

이 경우 `.env` 파일을 확인하고 해당 환경변수를 설정하세요.

---

## 참고

- [CONTRIBUTING.md](./CONTRIBUTING.md) — 개발 환경 세팅
- [CLAUDE.md](../CLAUDE.md) — 프로젝트 아키텍처
