"use client";

import { useState, useRef, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  ArrowLeft,
  Download,
  Camera,
  Highlighter,
  Instagram,
  Plus,
} from "lucide-react";
import { getMyBooks, getHighlights, addHighlight, generateAiBackground, getAiGenerationRemaining } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { useImageExport } from "@/hooks/useImageExport";
import { PageLoading } from "@/components/ui/LoadingSpinner";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import CoverCard from "@/components/image-generator/CoverCard";
import HighlightCard from "@/components/image-generator/HighlightCard";
import BackgroundSelector, { type BgTab } from "@/components/image-generator/BackgroundSelector";
import { COVER_THEMES, HIGHLIGHT_THEMES, FONT_OPTIONS, POSTIT_COLORS } from "@/components/image-generator/themes";
import type { Theme, AspectRatio, FontId, PostitColor } from "@/components/image-generator/themes";
import type { UserBook, Highlight } from "@/lib/types";

type CardType = "cover" | "highlight";

/** 북스타그램 이미지 생성 페이지 */
export default function CreateImagePage({
  params,
}: {
  params: Promise<{ userBookId: string }>;
}) {
  const { userBookId } = use(params);
  const { user, isLoading: authLoading } = useRequireAuth();
  const router = useRouter();
  const { exportToPng, isExporting, error: exportError } = useImageExport();
  const cardRef = useRef<HTMLDivElement | null>(null);

  // ── 상태 ─────────────────────────────────────────────
  const [cardType, setCardType] = useState<CardType>("cover");
  const [aspectRatio, setAspectRatio] = useState<AspectRatio>("4:5");
  const [bgTab, setBgTab] = useState<BgTab>("theme");
  const [coverTheme, setCoverTheme] = useState<Theme>(COVER_THEMES[0]);
  const [highlightTheme, setHighlightTheme] = useState<Theme>(HIGHLIGHT_THEMES[0]);
  const [uploadedBg, setUploadedBg] = useState<string | null>(null);
  const [aiImageUrl, setAiImageUrl] = useState<string | null>(null);
  const [aiRemaining, setAiRemaining] = useState(3);
  const [isGeneratingAi, setIsGeneratingAi] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [reviewText, setReviewText] = useState("");
  const [highlightText, setHighlightText] = useState("");
  const [selectedHighlightId, setSelectedHighlightId] = useState<string | null>(null);
  const [isAddingNew, setIsAddingNew] = useState(false);
  const [accountName, setAccountName] = useState("");
  const [bookTitle, setBookTitle] = useState("");
  const [selectedFont, setSelectedFont] = useState<FontId>("pretendard");
  const [postitColor, setPostitColor] = useState<PostitColor>(POSTIT_COLORS[0]);
  const [showInstagramNotice, setShowInstagramNotice] = useState(false);
  const [newHighlightSaved, setNewHighlightSaved] = useState(false);

  // ── 데이터 조회 ────────────────────────────────────────
  const { data: myBooks, isLoading: booksLoading } = useQuery({
    queryKey: ["myBooks"],
    queryFn: () => getMyBooks(),
    enabled: !!user,
  });

  const userBook = myBooks?.find((b: UserBook) => b.id === userBookId);

  const { data: highlights = [] } = useQuery<Highlight[]>({
    queryKey: ["highlights", userBookId],
    queryFn: () => getHighlights(userBookId),
    enabled: !!userBook && cardType === "highlight",
  });

  // ── 초기값 설정 ────────────────────────────────────────
  useEffect(() => {
    if (!userBook) return;
    setReviewText(userBook.memo ?? "");
    setBookTitle(userBook.book.title);
  }, [userBook]);

  useEffect(() => {
    if (!user) return;

    if (user.instagram_username) {
      setAccountName(`@${user.instagram_username}`);
      setShowInstagramNotice(false);
    } else {
      setAccountName(user.name);
      setShowInstagramNotice(true);
    }
  }, [user]);

  // ── 하이라이트 선택 시 텍스트 동기화 ────────────────────
  useEffect(() => {
    if (!selectedHighlightId) return;
    const found = highlights.find((h: Highlight) => h.id === selectedHighlightId);
    if (found) setHighlightText(found.content);
  }, [selectedHighlightId, highlights]);

  // ── AI 남은 횟수 초기 로드 ────────────────────────────
  useEffect(() => {
    if (!user) return;
    getAiGenerationRemaining()
      .then((res) => setAiRemaining(res.remaining))
      .catch(() => {});
  }, [user]);

  // ── AI 배경 생성 ──────────────────────────────────────
  const handleGenerateAi = async () => {
    if (!userBook || isGeneratingAi || aiRemaining === 0) return;
    setIsGeneratingAi(true);
    setAiError(null);
    try {
      const res = await generateAiBackground({
        book_id: userBook.book.id,
        title: userBook.book.title,
        author: userBook.book.author,
        genre: userBook.book.genre ?? undefined,
        description: userBook.book.description ?? undefined,
      });
      setAiRemaining(res.remaining_today);

      // DALL-E URL은 1시간 후 만료되므로 즉시 프록시를 통해 data URL로 변환
      const proxyUrl = `/api/proxy-image?url=${encodeURIComponent(res.image_url)}`;
      const imgResponse = await fetch(proxyUrl);
      if (!imgResponse.ok) throw new Error("이미지 다운로드 실패");
      const blob = await imgResponse.blob();
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
      setAiImageUrl(dataUrl);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "이미지 생성에 실패했어요. 다시 시도해주세요.";
      setAiError(msg);
    } finally {
      setIsGeneratingAi(false);
    }
  };

  // ── 하이라이트 저장 mutation ──────────────────────────
  const saveHighlightMutation = useMutation({
    mutationFn: () =>
      addHighlight({ user_book_id: userBookId, content: highlightText.trim() }),
    onSuccess: () => {
      setNewHighlightSaved(true);
    },
  });

  // ── 이미지 다운로드 ────────────────────────────────────
  const handleDownload = async () => {
    // 하이라이트 카드에서 새 텍스트 입력 시 DB 저장
    if (
      cardType === "highlight" &&
      isAddingNew &&
      highlightText.trim() &&
      !newHighlightSaved
    ) {
      try {
        await saveHighlightMutation.mutateAsync();
      } catch {
        // 저장 실패해도 이미지 다운로드는 계속 진행
      }
    }

    const book = userBook?.book;
    const filename = `${book?.title ?? "bookchiki"}_${cardType}_${aspectRatio.replace(":", "x")}.png`;
    await exportToPng(cardRef.current, { filename, scale: 3 });
  };

  const activeTheme = cardType === "cover" ? coverTheme : highlightTheme;
  // aiImageUrl은 이미 data URL로 저장됨 (프록시 변환 완료)
  const bgForCard =
    bgTab === "upload" && uploadedBg
      ? uploadedBg
      : bgTab === "ai" && aiImageUrl
        ? aiImageUrl
        : undefined;
  const activeFontFamily = FONT_OPTIONS.find((f) => f.id === selectedFont)?.fontFamily ?? FONT_OPTIONS[0].fontFamily;

  if (authLoading || booksLoading) return <PageLoading />;
  if (!userBook) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh] gap-4">
        <p style={{ color: "var(--text-muted)" }}>책 정보를 찾을 수 없어요.</p>
        <button
          type="button"
          onClick={() => router.back()}
          className="btn-primary"
        >
          돌아가기
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-0 max-w-5xl mx-auto">
      {/* 헤더 */}
      <div
        className="flex items-center gap-3 px-1 mb-6"
        style={{ borderBottom: "1px solid var(--border-default)", paddingBottom: "16px" }}
      >
        <button
          type="button"
          onClick={() => router.back()}
          className="p-1.5 rounded-xl cursor-pointer transition-colors"
          style={{ color: "var(--text-muted)", background: "var(--bg-subtle)" }}
        >
          <ArrowLeft size={18} />
        </button>
        <div>
          <h1 className="text-base font-bold" style={{ color: "var(--text-primary)" }}>
            이미지 만들기
          </h1>
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            {userBook.book.title}
          </p>
        </div>
      </div>

      {/* 인스타그램 미등록 알림 */}
      {showInstagramNotice && (
        <div
          className="flex items-start gap-3 rounded-2xl p-4 mb-4"
          style={{ background: "var(--accent-light)", border: "1px solid #FDE68A" }}
        >
          <Instagram size={15} style={{ color: "var(--accent-dark)", flexShrink: 0, marginTop: "1px" }} />
          <div className="flex-1 min-w-0">
            <p className="text-xs leading-relaxed" style={{ color: "#92400E" }}>
              인스타그램 계정이 등록되어 있지 않아 프로필 이름으로 생성됩니다.
              인스타그램 계정 등록은{" "}
              <button
                type="button"
                onClick={() => router.push("/mypage")}
                className="underline font-semibold cursor-pointer"
                style={{ color: "var(--accent-dark)" }}
              >
                마이페이지
              </button>
              에서 가능합니다.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowInstagramNotice(false)}
            className="text-xs cursor-pointer"
            style={{ color: "#92400E", opacity: 0.7, flexShrink: 0 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* 메인 영역: 좌(설정) + 우(미리보기) */}
      <div className="flex flex-col lg:flex-row gap-6">
        {/* ── 좌측: 설정 패널 ── */}
        <div className="flex flex-col gap-5 lg:w-80 flex-shrink-0">

          {/* STEP 1: 카드 타입 */}
          <Section title="카드 타입">
            <div className="flex gap-2">
              <TypeButton
                icon={<Camera size={14} />}
                label="표지 카드"
                active={cardType === "cover"}
                onClick={() => setCardType("cover")}
              />
              <TypeButton
                icon={<Highlighter size={14} />}
                label="하이라이트 카드"
                active={cardType === "highlight"}
                onClick={() => setCardType("highlight")}
              />
            </div>
          </Section>

          {/* STEP 2: 이미지 비율 */}
          <Section title="이미지 비율">
            <div className="flex gap-2">
              <RatioButton ratio="1:1" label="1:1" sub="1080×1080" active={aspectRatio === "1:1"} onClick={() => setAspectRatio("1:1")} />
              <RatioButton ratio="4:5" label="4:5" sub="1080×1350" active={aspectRatio === "4:5"} onClick={() => setAspectRatio("4:5")} />
            </div>
          </Section>

          {/* STEP 3: 배경 선택 */}
          <Section title="배경">
            <BackgroundSelector
              themes={cardType === "cover" ? COVER_THEMES : HIGHLIGHT_THEMES}
              activeTab={bgTab}
              onTabChange={(tab) => {
                setBgTab(tab);
                if (tab === "theme") { setUploadedBg(null); }
                if (tab === "upload") { setAiImageUrl(null); }
                if (tab === "ai") { setUploadedBg(null); }
              }}
              selectedThemeId={activeTheme.id}
              onThemeSelect={(t) => {
                if (cardType === "cover") setCoverTheme(t);
                else setHighlightTheme(t);
              }}
              uploadedBg={uploadedBg}
              onUpload={(url) => setUploadedBg(url)}
              onClearUpload={() => setUploadedBg(null)}
              aiImageUrl={aiImageUrl}
              aiRemaining={aiRemaining}
              aiLimit={3}
              isGenerating={isGeneratingAi}
              aiError={aiError}
              onGenerateAi={handleGenerateAi}
              onClearAi={() => setAiImageUrl(null)}
            />
          </Section>

          {/* STEP 4: 폰트 선택 */}
          <Section title="폰트">
            <div className="flex gap-2">
              {FONT_OPTIONS.map((font) => (
                <button
                  key={font.id}
                  type="button"
                  onClick={() => setSelectedFont(font.id)}
                  className="flex-1 py-2.5 rounded-xl text-xs cursor-pointer transition-all"
                  style={{
                    background: selectedFont === font.id ? "var(--accent-light)" : "var(--bg-subtle)",
                    border: `1.5px solid ${selectedFont === font.id ? "var(--accent)" : "var(--border-default)"}`,
                    color: selectedFont === font.id ? "var(--accent-dark)" : "var(--text-secondary)",
                    fontFamily: font.fontFamily,
                    fontWeight: selectedFont === font.id ? 700 : 400,
                  }}
                >
                  {font.name}
                </button>
              ))}
            </div>
          </Section>

          {/* STEP 5: 책 제목 편집 */}
          <Section title="책 제목">
            <input
              type="text"
              value={bookTitle}
              onChange={(e) => setBookTitle(e.target.value)}
              placeholder="카드에 표시할 책 제목"
              maxLength={60}
              className="w-full px-3 py-2 rounded-xl text-sm"
              style={{
                background: "var(--bg-subtle)",
                border: "1px solid var(--border-default)",
                color: "var(--text-primary)",
                outline: "none",
                fontFamily: activeFontFamily,
              }}
              onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
              onBlur={(e) => (e.target.style.borderColor = "var(--border-default)")}
            />
            <p className="text-[10px]" style={{ color: "var(--text-muted)" }}>
              부제목 포함 여부나 줄임 표현을 자유롭게 수정하세요
            </p>
          </Section>

          {/* 포스트잇 색상 선택 (하이라이트 카드 + 포스트잇 테마일 때만) */}
          {cardType === "highlight" && highlightTheme.id === "postit" && (
            <Section title="포스트잇 색상">
              <div className="flex gap-2 flex-wrap">
                {POSTIT_COLORS.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    title={c.name}
                    onClick={() => setPostitColor(c)}
                    className="cursor-pointer transition-all"
                    style={{
                      width: "32px",
                      height: "32px",
                      borderRadius: "8px",
                      background: c.bg,
                      border: postitColor.id === c.id
                        ? "2.5px solid var(--accent)"
                        : "2px solid var(--border-default)",
                      boxShadow: postitColor.id === c.id
                        ? "0 0 0 2px var(--accent-light)"
                        : "none",
                      flexShrink: 0,
                    }}
                  />
                ))}
              </div>
              <p className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                {postitColor.name}
              </p>
            </Section>
          )}

          {/* STEP 6: 텍스트 편집 */}
          {cardType === "cover" ? (
            <Section title="한 줄 리뷰">
              <textarea
                value={reviewText}
                onChange={(e) => setReviewText(e.target.value)}
                placeholder="이 책에 대한 한 줄 리뷰를 입력하세요"
                rows={3}
                maxLength={200}
                className="w-full px-3 py-2.5 text-sm rounded-xl resize-none"
                style={{
                  background: "var(--bg-subtle)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-primary)",
                  outline: "none",
                }}
                onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
                onBlur={(e) => (e.target.style.borderColor = "var(--border-default)")}
              />
              <p className="text-[10px] text-right" style={{ color: "var(--text-muted)" }}>
                {reviewText.length}/200
              </p>
            </Section>
          ) : (
            <Section title="하이라이트">
              {/* 하이라이트 목록이 있을 때 */}
              {highlights.length > 0 && (
                <div className="flex flex-col gap-1.5">
                  <p className="text-[11px] font-medium" style={{ color: "var(--text-muted)" }}>
                    등록된 하이라이트 선택
                  </p>

                  {highlights.map((h: Highlight) => (
                    <button
                      key={h.id}
                      type="button"
                      onClick={() => {
                        setSelectedHighlightId(h.id);
                        setHighlightText(h.content);
                        setIsAddingNew(false);
                        setNewHighlightSaved(true);
                      }}
                      className="w-full text-left px-3 py-2 rounded-xl text-xs cursor-pointer transition-colors"
                      style={{
                        background: selectedHighlightId === h.id ? "var(--accent-light)" : "var(--bg-subtle)",
                        border: `1px solid ${selectedHighlightId === h.id ? "#FDE68A" : "var(--border-default)"}`,
                        color: "var(--text-primary)",
                        lineHeight: 1.6,
                      }}
                    >
                      <span className="line-clamp-2">{h.content}</span>
                    </button>
                  ))}

                  {/* 추가하기 버튼 — 목록 마지막 */}
                  {!isAddingNew && (
                    <button
                      type="button"
                      onClick={() => {
                        setIsAddingNew(true);
                        setSelectedHighlightId(null);
                        setHighlightText("");
                        setNewHighlightSaved(false);
                      }}
                      className="w-full flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-medium cursor-pointer transition-colors"
                      style={{
                        border: "1.5px dashed var(--border-default)",
                        color: "var(--text-muted)",
                        background: "transparent",
                      }}
                    >
                      <Plus size={12} />
                      하이라이트 추가하기
                    </button>
                  )}
                </div>
              )}

              {/* 텍스트박스: 하이라이트 선택됐거나 / 추가하기 클릭했거나 / 목록 없을 때 */}
              {(selectedHighlightId || isAddingNew || highlights.length === 0) && (
                <div className="flex flex-col gap-1.5 mt-1">
                  <p className="text-[11px] font-medium" style={{ color: "var(--text-muted)" }}>
                    {selectedHighlightId ? "수정하기" : "인상 깊은 문장 입력"}
                  </p>
                  <textarea
                    value={highlightText}
                    onChange={(e) => {
                      setHighlightText(e.target.value);
                      setSelectedHighlightId(null);
                      setIsAddingNew(true);
                      setNewHighlightSaved(false);
                    }}
                    placeholder="인상 깊은 문장을 입력하세요"
                    rows={4}
                    maxLength={300}
                    className="w-full px-3 py-2.5 text-sm rounded-xl resize-none"
                    style={{
                      background: "var(--bg-subtle)",
                      border: "1px solid var(--border-default)",
                      color: "var(--text-primary)",
                      outline: "none",
                    }}
                    onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
                    onBlur={(e) => (e.target.style.borderColor = "var(--border-default)")}
                  />
                  {isAddingNew && highlightText.trim() && !newHighlightSaved && (
                    <p className="text-[10px]" style={{ color: "var(--text-muted)" }}>
                      * 다운로드 시 하이라이트로 자동 저장됩니다
                    </p>
                  )}
                  {newHighlightSaved && isAddingNew && (
                    <p className="text-[10px]" style={{ color: "var(--status-read)" }}>
                      ✓ 하이라이트로 저장됐어요
                    </p>
                  )}
                </div>
              )}
            </Section>
          )}

          {/* STEP 7: 계정명 */}
          <Section title="계정명">
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={accountName}
                onChange={(e) => setAccountName(e.target.value)}
                placeholder="계정명"
                maxLength={40}
                className="flex-1 px-3 py-2 rounded-xl text-sm"
                style={{
                  background: "var(--bg-subtle)",
                  border: "1px solid var(--border-default)",
                  color: "var(--text-primary)",
                  outline: "none",
                }}
                onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
                onBlur={(e) => (e.target.style.borderColor = "var(--border-default)")}
              />
            </div>
          </Section>
        </div>

        {/* ── 우측: 미리보기 + 다운로드 ── */}
        <div className="flex flex-col items-center gap-4 flex-1">
          <div
            className="flex flex-col items-center gap-3 p-5 rounded-3xl w-full"
            style={{ background: "var(--bg-subtle)", border: "1px solid var(--border-default)" }}
          >
            <p className="text-xs font-semibold self-start" style={{ color: "var(--text-muted)" }}>
              미리보기
            </p>

            {/* 카드 렌더러 */}
            <div
              style={{
                borderRadius: "12px",
                overflow: "hidden",
                boxShadow: "0 8px 32px rgba(0,0,0,0.15)",
              }}
            >
              {cardType === "cover" ? (
                <CoverCard
                  userBook={userBook}
                  theme={coverTheme}
                  aspectRatio={aspectRatio}
                  reviewText={reviewText}
                  accountName={accountName}
                  bookTitle={bookTitle}
                  fontFamily={activeFontFamily}
                  customBackground={bgForCard}
                  cardRef={cardRef}
                />
              ) : (
                <HighlightCard
                  userBook={userBook}
                  theme={highlightTheme}
                  aspectRatio={aspectRatio}
                  highlightText={highlightText}
                  accountName={accountName}
                  bookTitle={bookTitle}
                  fontFamily={activeFontFamily}
                  postitColor={postitColor}
                  customBackground={bgForCard}
                  cardRef={cardRef}
                />
              )}
            </div>

            {/* 다운로드 버튼 */}
            <button
              type="button"
              onClick={handleDownload}
              disabled={isExporting || saveHighlightMutation.isPending}
              className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl text-sm font-semibold cursor-pointer transition-all"
              style={{
                background: "var(--accent)",
                color: "white",
                border: "none",
                opacity: isExporting ? 0.7 : 1,
              }}
            >
              {isExporting ? (
                <>
                  <LoadingSpinner size={16} />
                  이미지 생성 중...
                </>
              ) : (
                <>
                  <Download size={16} />
                  PNG 다운로드 (고해상도)
                </>
              )}
            </button>

            {exportError && (
              <p className="text-xs" style={{ color: "#EF4444" }}>
                {exportError}
              </p>
            )}

            <p className="text-[10px] text-center" style={{ color: "var(--text-muted)" }}>
              실제 저장 이미지는 1080px 기준으로 생성돼요
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── 내부 UI 컴포넌트들 ────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs font-semibold" style={{ color: "var(--text-muted)" }}>
        {title}
      </p>
      {children}
    </div>
  );
}

function TypeButton({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs font-medium cursor-pointer transition-all"
      style={{
        background: active ? "var(--accent)" : "var(--bg-subtle)",
        color: active ? "white" : "var(--text-secondary)",
        border: `1px solid ${active ? "var(--accent)" : "var(--border-default)"}`,
      }}
    >
      {icon}
      {label}
    </button>
  );
}

function RatioButton({
  ratio,
  label,
  sub,
  active,
  onClick,
}: {
  ratio: AspectRatio;
  label: string;
  sub: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex-1 flex flex-col items-center gap-0.5 py-3 rounded-xl cursor-pointer transition-all"
      style={{
        background: active ? "var(--accent-light)" : "var(--bg-subtle)",
        border: `1.5px solid ${active ? "var(--accent)" : "var(--border-default)"}`,
      }}
    >
      {/* 비율 시각화 */}
      <div
        style={{
          width: ratio === "1:1" ? "24px" : "19px",
          height: ratio === "1:1" ? "24px" : "24px",
          borderRadius: "3px",
          border: `1.5px solid ${active ? "var(--accent)" : "var(--text-muted)"}`,
          marginBottom: "4px",
        }}
      />
      <span
        className="text-xs font-semibold"
        style={{ color: active ? "var(--accent-dark)" : "var(--text-secondary)" }}
      >
        {label}
      </span>
      <span
        className="text-[9px]"
        style={{ color: active ? "var(--accent-dark)" : "var(--text-muted)", opacity: 0.8 }}
      >
        {sub}
      </span>
    </button>
  );
}
