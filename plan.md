# 📚 독서 기록 + AI 책 추천 서비스 — Claude Code 플랜

## 프로젝트 개요

사용자의 독서 기록과 별점을 기반으로 AI가 책을 추천해주는 개인화 독서 서비스.
북스타그램 운영자를 위한 인스타 카드 이미지 생성은 부가 기능으로 제공한다.

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프론트엔드 | Next.js (App Router) + Tailwind CSS |
| 백엔드 | FastAPI (Python) |
| 메인 DB | PostgreSQL (유저, 책, 이미지 메타데이터) |
| 검색/벡터 | OpenSearch (책 시맨틱 검색 + 벡터 인덱싱) |
| AI | Claude API (RAG, Agent, 텍스트 생성) + DALL-E 3 또는 Stable Diffusion (이미지 생성) |
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

### Phase 1 — 기반 인프라 (1주차)
- [x] FastAPI 프로젝트 세팅 (디렉토리 구조, 환경변수)
- [x] PostgreSQL 연결 + SQLAlchemy ORM 모델 정의
- [x] AWS EC2 인스턴스 생성 + Docker 배포 세팅
- [ ] AWS S3 버킷 생성 + 이미지 업로드 유틸 함수
- [ ] Google OAuth 인증 구현
- [ ] Next.js 프로젝트 세팅 + Vercel 배포 연결

### Phase 2 — 독서 기록 (메인 기능 1) (2주차 전반)
- [x] 알라딘 API 연동 (책 검색 + 정보 수집 + 선택 저장)
- [x] 별점 + 메모 + 하이라이터 입력 API
- [x] 북적북적 CSV/JSON 임포트 파싱 로직 (중복 감지 포함)
- [x] 독서 통계 집계 API (월별 독서량, 장르 분포, 평균 별점) + 라우트 버그 픽스

### Phase 3 — OpenSearch + AI 추천 (메인 기능 2) (2주차 후반 ~ 3주차)
- [x] AWS OpenSearch 클러스터 생성 (개발 중엔 로컬 Docker)
- [x] 책 인덱스 매핑 설계 (키워드 필드 + 벡터 필드)
- [x] 책 설명 임베딩 생성 후 OpenSearch 인덱싱
- [x] 별점 가중치 반영 취향 벡터 계산 로직
- [x] OpenSearch KNN으로 유사 도서 탐색 API
- [x] OpenAI(GPT-4o-mini) API 연동 → 추천 이유 코멘트 생성
- [x] 자연어 책 검색 (하이브리드 검색: 키워드 + KNN)
- [x] 추천 캐싱 전략 (별점 변경 시 캐시 무효화)

### Phase 4 — 이미지 생성 (부가 기능) (3주차 후반)
- [ ] AI Agent Tool 정의
  - `extract_book_quote`: RAG로 핵심 문구 추출
  - `generate_image_prompt`: 이미지 프롬프트 생성
  - `create_image`: DALL-E 3 이미지 생성
- [ ] Agent 오케스트레이션 로직
- [ ] 생성 이미지 S3 저장 + DB 기록
- [ ] Canvas API 기반 텍스트 편집 에디터 (폰트 / 색상 / 위치 수정)
- [ ] image_versions 테이블로 버전 관리

### Phase 5 — 프론트엔드 (4주차)
- [ ] 메인 페이지 (서비스 소개 + 독서 통계 대시보드)
- [ ] 내 서재 페이지 (독서 기록 목록, 상태 필터, 별점/메모 입력)
- [ ] 책 추천 페이지 (추천 리스트 + AI 추천 이유)
- [ ] 책 검색 페이지 (자연어 검색)
- [ ] 외부 앱 임포트 페이지 (파일 업로드 → 결과 리포트)
- [ ] 이미지 생성 페이지 (책 입력 → 스타일 선택 → 생성 → 텍스트 편집 → 다운로드)
- [ ] 마이페이지 (독서 통계, 생성 이미지 히스토리)

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
