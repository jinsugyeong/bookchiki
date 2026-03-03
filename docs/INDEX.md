# 문서 인덱스

마지막 업데이트: 2026-03-03 (Phase 5 프론트엔드 완료 + Refresh Token 구현)

Bookchiki 프로젝트의 모든 문서를 한 곳에서 찾을 수 있습니다.

---

## 핵심 문서

### 1. [CONTRIBUTING.md](./CONTRIBUTING.md) - 개발 환경 가이드
개발 환경 세팅, 서비스 실행 방법, 데이터베이스 관리, 문제 해결.

**대상:** 개발자 온보딩, 로컬 개발 환경 구성

**주요 내용:**
- 초기 세팅 (저장소 클론, 환경변수, 가상환경)
- Docker Compose로 전체 서비스 실행
- 로컬 백엔드 실행 (Docker 없이)
- DB 초기화 및 마이그레이션
- 개발 환경 인증 우회
- 문제 해결 (PostgreSQL, OpenSearch, JWT)

---

### 2. [ENV.md](./ENV.md) - 환경변수 레퍼런스
모든 환경변수의 설명, 형식, 기본값, 개발/프로덕션 설정 예시.

**대상:** 환경 구성, 배포 준비

**주요 내용:**
- 필수 환경변수 (Database, OAuth, JWT, API 키)
- 선택사항 환경변수 (기본값 제공)
- AWS S3 설정 (이미지 저장용)
- 로컬 개발 환경 설정 예시
- 프로덕션 배포 설정 예시
- 보안 주의사항

---

### 3. [API.md](./API.md) - API 엔드포인트 레퍼런스
모든 API 엔드포인트의 경로, 파라미터, 요청/응답 형식, 동작 설명.

**대상:** 프론트엔드 개발, API 통합, 테스트

**주요 내용:**
- 인증 (Google OAuth, JWT)
- 도서 관리 (조회, 검색, 추가)
- 내 서재 (통계, 목록, 추가, 수정, 삭제)
- 하이라이트 & 메모
- 추천 시스템 1 (기록 기반, OpenSearch 하이브리드)
- 추천 시스템 2 (질문 기반, RAG)
- CSV 가져오기
- 관리자 기능 (인덱싱, 시딩)
- 에러 응답 형식

---

## 아키텍처 & 설계 문서

### [CLAUDE.md](../CLAUDE.md) - 프로젝트 개요 및 아키텍처
프로젝트 소개, 기술 스택, 핵심 기능, 시스템 아키텍처, 데이터 모델, 서비스 구조.

**대상:** 전체 프로젝트 이해, 기여 계획 수립

---

### [recommendation-profile-cache-design.md](./recommendation-profile-cache-design.md) - 추천 파이프라인 설계
추천 시스템의 프로필 캐싱, 취향 벡터 계산, 성능 최적화 상세 설명.

**대상:** 추천 기능 이해, 최적화, 확장

---

## 개발 흐름

### 처음 시작하는 개발자

1. **[CONTRIBUTING.md](./CONTRIBUTING.md)** 읽기
   - 로컬 환경 세팅
   - Docker Compose로 서비스 시작

2. **[ENV.md](./ENV.md)** 참고
   - API 키 설정 (Google, Aladin, OpenAI)
   - 개발 환경 특수 설정 (APP_ENV=development)

3. **[API.md](./API.md)** 참고
   - 엔드포인트 이해
   - Swagger UI (http://localhost:8000/docs) 탐색

4. **[CLAUDE.md](../CLAUDE.md)** 정독
   - 프로젝트 구조 이해
   - 핵심 패턴 학습

---

### API 개발

1. **[API.md](./API.md)** — 엔드포인트 스펙 확인
2. **코드 작성** — `backend/app/api/` 구현
3. **테스트** — Swagger UI 또는 curl/Postman으로 테스트
4. **[CLAUDE.md](../CLAUDE.md)** — 아키텍처 패턴 준수 확인

---

### 프론트엔드 개발 (Phase 5 완료)

1. **[프론트엔드 개발 시작](./frontend-guide.md)** (있으면 참고)
2. 프론트엔드 구조: `frontend/` — Next.js 15, Tailwind v4, TanStack Query v5
3. 개발 서버: `cd frontend && npm run dev` → http://localhost:3000
4. 주요 페이지:
   - `/` (홈)
   - `/login` (Google OAuth)
   - `/library` (내 서재)
   - `/library/search` (책 검색)
   - `/recommendations` (추천)
   - `/mypage` (마이페이지)
5. API 통합: `frontend/services/api-client.ts`로 백엔드와 자동 통신

---

### 추천 기능 개발 (Phase 4 완료, Phase 5 구현됨)

1. **[recommendation-profile-cache-design.md](./recommendation-profile-cache-design.md)** — 캐시 아키텍처 설계
2. **[CLAUDE.md](../CLAUDE.md)** — 추천 파이프라인 섹션 정독
3. **[plan.md](./plan.md)** — Phase 4 구현 태스크 확인
4. **[API.md](./API.md)** — `/recommendations`, `/recommendations/ask`, `/recommendations/profile`, `/admin/index-books`, `/admin/index-memos` 엔드포인트 확인
5. 서비스 코드: `recommend.py`, `profile_cache.py`, `book_indexer.py`(신규), `memo_indexer.py`(신규), `book_search.py`(신규)
6. 모델: `backend/app/models/user_preference_profile.py`

---

### 배포 준비

1. **[ENV.md](./ENV.md)** — 프로덕션 환경변수 설정
2. **[CLAUDE.md](../CLAUDE.md)** — 보안 검토
3. 배포 파이프라인 구성

---

## 파일 매핑

| 문서 | 관련 파일 |
|------|---------|
| CONTRIBUTING.md | `backend/`, `docker-compose.yml`, `requirements.txt` |
| ENV.md | `backend/.env`, `backend/.env.example`, `app/core/config.py` |
| API.md | `backend/app/api/` (모든 라우터 파일), 특히 `recommendations.py`, `user_books.py`, `imports.py` |
| CLAUDE.md | 전체 프로젝트 아키텍처 (Phase 4 재설계 반영) |
| recommendation-profile-cache-design.md | `recommend.py`, `profile_cache.py`, `book_indexer.py`(신규), `memo_indexer.py`(신규), `book_search.py`(신규), `user_preference_profile.py` |
| plan.md | Phase 4 추천 시스템 재설계 태스크 |

---

## 자주 찾는 정보

### "로컬 개발 환경을 어떻게 세팅하나요?"
→ [CONTRIBUTING.md](./CONTRIBUTING.md) - "초기 세팅" 섹션

### "어떤 환경변수가 필요한가요?"
→ [ENV.md](./ENV.md) - "필수 환경변수" 테이블

### "Google OAuth 없이 개발할 수 있나요?"
→ [ENV.md](./ENV.md) - "개발 환경 팁" 섹션

### "API 응답 형식이 뭔가요?"
→ [API.md](./API.md) - 각 엔드포인트의 "응답" 섹션

### "서비스 시작 명령어가 뭐예요?"
→ [CONTRIBUTING.md](./CONTRIBUTING.md) - "주요 커맨드 정리" 테이블

### "PostgreSQL 연결 오류는 왜 발생하나요?"
→ [CONTRIBUTING.md](./CONTRIBUTING.md) - "문제 해결" 섹션

### "추천 시스템이 어떻게 작동하나요?"
→ 시스템 1 (기록 기반): [CLAUDE.md](../CLAUDE.md) - "추천 파이프라인" 섹션

→ 시스템 2 (자연어 질문 기반): [plan.md](./plan.md) - "Phase 3.5 추천 시스템 아키텍처 결정" 섹션

→ Phase 4 재설계: [recommendation-profile-cache-design.md](./recommendation-profile-cache-design.md)

### "추천 시스템 1과 시스템 2의 차이는 무엇인가요?"

→ **시스템 1** (`GET /recommendations`): 유저 서재/메모 기반 자동 개인화 추천 (OpenSearch 하이브리드 검색)

→ **시스템 2** (`POST /recommendations/ask`): 유저가 자연어로 직접 질문하면 RAG 기반 맞춤 추천

→ [API.md](./API.md) - 추천 섹션 참고

### "추천 캐시가 정확히 어떻게 작동하나요?"
→ [recommendation-profile-cache-design.md](./recommendation-profile-cache-design.md) - "5. 추천 흐름 설계" + "6. Dirty 마킹 전략" 섹션

### "프로젝트 전체 구조가 뭔가요?"
→ [CLAUDE.md](../CLAUDE.md) - "아키텍처" 섹션

---

## 문서 유지보수 규칙

- **AUTO-GENERATED 섹션:** 자동 업데이트 대상 (코드에서 추출)
- **마지막 업데이트:** 각 문서 상단의 `마지막 업데이트` 타임스탬프 확인
- **정보 정확성:** 코드와 문서가 일치하지 않으면 코드가 우선



---

**생성 일자:** 2026-02-22
**버전:** 1.0
