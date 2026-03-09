"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Star,
  Sparkles,
  MessageCircle,
  RefreshCw,
  Send,
  BookOpen,
} from "lucide-react";
import { getRecommendations, askRecommendation, refreshRecommendations, dismissRecommendation } from "@/lib/api";
import type { Recommendation } from "@/lib/types";
import RecommendCard from "@/components/recommendations/RecommendCard";
import { PageLoading, SkeletonCard } from "@/components/ui/LoadingSpinner";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import { useRequireAuth } from "@/hooks/useRequireAuth";

type Tab = "system1" | "system2";

/** 추천 페이지 — 시스템 1 (기록 기반) + 시스템 2 (질문 기반) */
export default function RecommendationsPage() {
  const { user, isLoading: authLoading } = useRequireAuth();
  const [activeTab, setActiveTab] = useState<Tab>("system1");

  if (authLoading) return <PageLoading />;
  if (!user) return null;

  return (
    <div className="flex flex-col gap-5">
      {/* 페이지 헤더 */}
      <div>
        <h1 className="text-xl font-extrabold" style={{ color: "var(--text-primary)" }}>
          AI 책 추천
        </h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-muted)" }}>
          내 독서 기록을 분석해서 딱 맞는 책을 골라드려요
        </p>
      </div>

      {/* 탭 */}
      <div
        className="flex gap-1 p-1 rounded-2xl"
        style={{ background: "var(--bg-subtle)", border: "1px solid var(--border-default)" }}
      >
        <TabButton
          active={activeTab === "system1"}
          onClick={() => setActiveTab("system1")}
          icon={Star}
          label="취향 기반 추천"
          desc="내 독서 기록 분석"
        />
        <TabButton
          active={activeTab === "system2"}
          onClick={() => setActiveTab("system2")}
          icon={MessageCircle}
          label="질문 기반 추천"
          desc="원하는 책을 말해봐요"
        />
      </div>

      {/* 탭 콘텐츠 */}
      {activeTab === "system1" ? <System1Tab /> : <System2Tab />}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon: Icon,
  label,
  desc,
}: {
  active: boolean;
  onClick: () => void;
  icon: typeof Star;
  label: string;
  desc: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex-1 flex items-center gap-2.5 px-4 py-3 rounded-xl transition-all cursor-pointer"
      style={{
        background: active ? "var(--bg-card)" : "transparent",
        boxShadow: active ? "var(--shadow-sm)" : "none",
      }}
    >
      <div
        className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
        style={{
          background: active ? "var(--accent-light)" : "transparent",
        }}
      >
        <Icon size={16} color={active ? "var(--accent-dark)" : "var(--text-muted)"} strokeWidth={2} />
      </div>
      <div className="text-left min-w-0">
        <p
          className="text-sm font-semibold leading-tight"
          style={{ color: active ? "var(--text-primary)" : "var(--text-muted)" }}
        >
          {label}
        </p>
        <p
          className="text-[11px] mt-0.5 truncate"
          style={{ color: "var(--text-muted)" }}
        >
          {desc}
        </p>
      </div>
    </button>
  );
}

/** 시스템 1: 기록 기반 추천 */
function System1Tab() {
  const queryClient = useQueryClient();
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const { data, isLoading, error } = useQuery({
    queryKey: ["recommendations"],
    queryFn: () => getRecommendations(6),
    staleTime: 0, // 항상 서버에서 최신 데이터 (dismiss/서재 추가 반영)
  });

  const refreshMutation = useMutation({
    mutationFn: () => refreshRecommendations(6),
    onSuccess: (newData) => {
      queryClient.setQueryData(["recommendations"], newData);
      setDismissed(new Set());
    },
  });

  const handleDislike = async (bookId: string) => {
    setDismissed((prev) => new Set([...prev, bookId]));
    try {
      await dismissRecommendation(bookId);
      // 서버 dismiss 완료 후 캐시 무효화 → 다음 렌더에서 서버 데이터 반영
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    } catch {
      // 서버 저장 실패해도 클라이언트 dismiss는 유지
    }
  };

  const visibleRecs = (data?.recommendations ?? [])
    .filter((r) => !dismissed.has(r.book_id))
    .slice(0, 3);

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {[...Array(3)].map((_, i) => (
          <SkeletonCard key={i} className="h-64" />
        ))}
      </div>
    );
  }

  if (error) {
    return <ErrorState onRetry={() => queryClient.invalidateQueries({ queryKey: ["recommendations"] })} />;
  }

  if (!data || data.recommendations.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="flex flex-col gap-4">
      {/* 메타 정보 + 새로고침 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Sparkles size={14} style={{ color: "var(--accent)" }} />
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            {data.cache_status === "hit" ? "캐시에서 불러옴" : "새로 분석됨"}
            {data.profile_computed_at && ` · ${new Date(data.profile_computed_at).toLocaleDateString("ko-KR")}`}
          </span>
        </div>
        <button
          type="button"
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-xl transition-colors cursor-pointer"
          style={{
            color: "var(--text-secondary)",
            background: "var(--bg-subtle)",
            border: "1px solid var(--border-default)",
          }}
        >
          {refreshMutation.isPending ? (
            <LoadingSpinner size={12} />
          ) : (
            <RefreshCw size={13} />
          )}
          새로 분석
        </button>
      </div>

      {/* 추천 카드 3개 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {visibleRecs.map((rec, idx) => (
          <div
            key={rec.book_id}
            className="animate-fade-in"
            style={{ animationDelay: `${idx * 60}ms` }}
          >
            <RecommendCard
              recommendation={rec}
              onDislike={() => handleDislike(rec.book_id)}
              isRefreshing={refreshMutation.isPending}
            />
          </div>
        ))}
      </div>

      {visibleRecs.length === 0 && dismissed.size > 0 && (
        <div className="flex flex-col items-center gap-3 py-12">
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            더 보여줄 추천이 없어요
          </p>
          <button
            type="button"
            onClick={() => refreshMutation.mutate()}
            className="btn-primary text-sm"
          >
            <RefreshCw size={14} />
            새 추천 받기
          </button>
        </div>
      )}
    </div>
  );
}

/** 시스템 2: 질문 기반 추천 */
function System2Tab() {
  const [question, setQuestion] = useState("");
  const [results, setResults] = useState<Recommendation[]>([]);
  const [submitted, setSubmitted] = useState(false);

  const askMutation = useMutation({
    mutationFn: () => askRecommendation(question),
    onSuccess: (data) => {
      setResults(data.recommendations.slice(0, 3));
      setSubmitted(true);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (question.trim()) askMutation.mutate();
  };

  const EXAMPLE_QUESTIONS = [
    "감동적인 가족 이야기 추천해줘",
    "자기계발인데 너무 뻔하지 않은 책",
    "한 번 읽으면 멈출 수 없는 소설",
    "철학을 쉽게 풀어쓴 책",
  ];

  return (
    <div className="flex flex-col gap-5">
      {/* 질문 폼 */}
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <div
          className="rounded-2xl overflow-hidden"
          style={{ border: "1px solid var(--border-default)" }}
        >
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="읽고 싶은 책의 분위기나 주제를 자유롭게 말해봐요..."
            rows={3}
            className="w-full px-4 py-3.5 text-sm resize-none"
            style={{
              background: "var(--bg-card)",
              color: "var(--text-primary)",
              outline: "none",
              border: "none",
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleSubmit(e as any);
            }}
          />
          <div
            className="flex items-center justify-between px-4 py-2.5"
            style={{ borderTop: "1px solid var(--border-default)", background: "var(--bg-subtle)" }}
          >
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>
              Ctrl+Enter로 전송
            </span>
            <button
              type="submit"
              disabled={!question.trim() || askMutation.isPending}
              className="btn-primary text-xs py-2"
            >
              {askMutation.isPending ? <LoadingSpinner size={13} /> : <Send size={13} />}
              추천 받기
            </button>
          </div>
        </div>

        {/* 예시 질문 */}
        {!submitted && (
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => setQuestion(q)}
                className="px-3 py-1.5 rounded-xl text-xs font-medium transition-colors cursor-pointer"
                style={{
                  background: "var(--bg-card)",
                  color: "var(--text-secondary)",
                  border: "1px solid var(--border-default)",
                }}
              >
                {q}
              </button>
            ))}
          </div>
        )}
      </form>

      {/* 결과 */}
      {askMutation.isPending && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {[...Array(3)].map((_, i) => (
            <SkeletonCard key={i} className="h-64" />
          ))}
        </div>
      )}

      {!askMutation.isPending && results.length > 0 && (
        <div className="flex flex-col gap-4">
          <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            AI 추천 결과
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {results.map((rec, idx) => (
              <div
                key={rec.book_id}
                className="animate-fade-in"
                style={{ animationDelay: `${idx * 60}ms` }}
              >
                <RecommendCard recommendation={rec} showScore={false} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div
      className="flex flex-col items-center gap-4 py-20 rounded-3xl"
      style={{ background: "var(--bg-subtle)", border: "1px solid var(--border-default)" }}
    >
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center"
        style={{ background: "var(--accent-light)" }}
      >
        <BookOpen size={24} style={{ color: "var(--accent)" }} />
      </div>
      <div className="text-center">
        <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          추천을 받으려면 서재에 책을 먼저 추가해야 해요
        </p>
        <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
          읽은 책과 별점을 기록할수록 더 정확한 추천을 드려요
        </p>
      </div>
    </div>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div
      className="flex flex-col items-center gap-4 py-20 rounded-3xl"
      style={{ background: "var(--bg-subtle)", border: "1px solid var(--border-default)" }}
    >
      <p className="text-sm" style={{ color: "var(--text-muted)" }}>
        추천을 불러오지 못했어요
      </p>
      <button onClick={onRetry} className="btn-secondary text-sm">
        <RefreshCw size={14} />
        다시 시도
      </button>
    </div>
  );
}
