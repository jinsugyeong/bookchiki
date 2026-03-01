"use client";

import { useState, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  User,
  Upload,
  FileText,
  CheckCircle,
  AlertCircle,
  Sparkles,
  LogOut,
  Trash2,
  AlertTriangle,
  X,
} from "lucide-react";
import Image from "next/image";
import { importCSV, getUserProfile, deleteAccount } from "@/lib/api";
import type { ImportResult } from "@/lib/types";
import LoadingSpinner from "@/components/ui/LoadingSpinner";
import { useAuth } from "@/contexts/AuthContext";
import { useRequireAuth } from "@/hooks/useRequireAuth";
import { PageLoading } from "@/components/ui/LoadingSpinner";

/** 마이페이지 */
export default function MyPage() {
  const { user, isLoading } = useRequireAuth();
  if (isLoading) return <PageLoading />;
  if (!user) return null;

  return (
    <div className="flex flex-col gap-6 max-w-2xl mx-auto">
      {/* 헤더 */}
      <div>
        <h1 className="text-xl font-extrabold" style={{ color: "var(--text-primary)" }}>
          마이페이지
        </h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--text-muted)" }}>
          내 정보와 설정을 관리해요
        </p>
      </div>

      {/* 프로필 카드 */}
      <ProfileCard />

      {/* 취향 프로필 */}
      <TasteProfile />

      {/* CSV 임포트 */}
      <CSVImport />

      {/* 계정 관리 */}
      <AccountManagement />
    </div>
  );
}

/** 프로필 카드 — 실제 로그인 유저 정보 표시 */
function ProfileCard() {
  const { user, logout } = useAuth();

  return (
    <div className="card p-5 flex items-center gap-4">
      {/* 프로필 이미지 or 기본 아이콘 */}
      <div
        className="w-14 h-14 rounded-2xl flex items-center justify-center flex-shrink-0 overflow-hidden"
        style={{ background: "var(--accent-light)", border: "1px solid var(--border-default)" }}
      >
        {user?.profile_image ? (
          <Image
            src={user.profile_image}
            alt={user.name}
            width={56}
            height={56}
            className="w-full h-full object-cover"
            unoptimized
          />
        ) : (
          <User size={24} style={{ color: "var(--accent)" }} />
        )}
      </div>

      {/* 유저 정보 */}
      <div className="flex-1 min-w-0">
        <p className="text-base font-bold truncate" style={{ color: "var(--text-primary)" }}>
          {user?.name ?? "로그인 필요"}
        </p>
        <p className="text-sm truncate" style={{ color: "var(--text-muted)" }}>
          {user?.email ?? ""}
        </p>
        {user && (
          <span
            className="badge text-[11px] mt-1"
            style={{ background: "var(--accent-light)", color: "var(--accent-dark)" }}
          >
            Google 계정
          </span>
        )}
      </div>

      {/* 로그아웃 버튼 */}
      {user && (
        <button
          type="button"
          onClick={logout}
          className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-colors cursor-pointer flex-shrink-0"
          style={{
            color: "var(--text-muted)",
            background: "var(--bg-subtle)",
            border: "1px solid var(--border-default)",
          }}
        >
          <LogOut size={13} />
          로그아웃
        </button>
      )}
    </div>
  );
}

/** 취향 프로필 */
function TasteProfile() {
  const { data: profile, isLoading } = useQuery({
    queryKey: ["userProfile"],
    queryFn: getUserProfile,
  });

  return (
    <div className="card p-5 flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Sparkles size={16} style={{ color: "var(--accent)" }} />
        <h2 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
          AI 분석 취향 프로필
        </h2>
        {profile?.is_dirty && (
          <span
            className="badge text-[11px]"
            style={{ background: "#FEF3C7", color: "#92400E" }}
          >
            업데이트 필요
          </span>
        )}
      </div>

      {isLoading ? (
        <div className="flex justify-center py-4">
          <LoadingSpinner size={20} />
        </div>
      ) : !profile?.profile_data ? (
        <div
          className="rounded-xl p-4 text-center"
          style={{ background: "var(--bg-subtle)" }}
        >
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>
            아직 취향 프로필이 없어요. 책을 추가하고 별점을 남겨보세요!
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {profile.profile_data.preference_summary && (
            <div
              className="rounded-xl p-4"
              style={{ background: "var(--accent-light)", border: "1px solid #FDE68A" }}
            >
              <p className="text-xs leading-relaxed" style={{ color: "#92400E" }}>
                {profile.profile_data.preference_summary}
              </p>
            </div>
          )}

          {(profile.profile_data.preferred_genres?.length ?? 0) > 0 && (
            <div>
              <p className="text-xs font-semibold mb-2" style={{ color: "var(--text-muted)" }}>
                선호 장르
              </p>
              <div className="flex flex-wrap gap-1.5">
                {profile.profile_data.preferred_genres!.map((genre) => (
                  <span
                    key={genre}
                    className="badge"
                    style={{ background: "var(--status-read-bg)", color: "var(--status-read)" }}
                  >
                    {genre}
                  </span>
                ))}
              </div>
            </div>
          )}

          {(profile.profile_data.disliked_genres?.length ?? 0) > 0 && (
            <div>
              <p className="text-xs font-semibold mb-2" style={{ color: "var(--text-muted)" }}>
                덜 선호하는 장르
              </p>
              <div className="flex flex-wrap gap-1.5">
                {profile.profile_data.disliked_genres!.map((genre) => (
                  <span
                    key={genre}
                    className="badge"
                    style={{ background: "var(--bg-subtle)", color: "var(--text-muted)" }}
                  >
                    {genre}
                  </span>
                ))}
              </div>
            </div>
          )}

          {profile.profile_computed_at && (
            <p className="text-[11px]" style={{ color: "var(--text-muted)" }}>
              마지막 분석: {new Date(profile.profile_computed_at).toLocaleDateString("ko-KR")}
              {" · "}버전 {profile.version}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** CSV 임포트 섹션 */
function CSVImport() {
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const importMutation = useMutation({
    mutationFn: importCSV,
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["myBooks"] });
      queryClient.invalidateQueries({ queryKey: ["myStats"] });
    },
  });

  const handleFile = (file: File) => {
    if (!file.name.endsWith(".csv")) {
      alert("CSV 파일만 업로드할 수 있어요.");
      return;
    }
    setResult(null);
    importMutation.mutate(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  return (
    <div className="card p-5 flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Upload size={16} style={{ color: "var(--accent)" }} />
        <h2 className="text-sm font-bold" style={{ color: "var(--text-primary)" }}>
          독서 기록 가져오기
        </h2>
      </div>

      <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>
        북적북적 앱의 CSV 파일을 가져올 수 있어요.<br />
        기존 서재와 중복되는 책은 자동으로 건너뜁니다.
      </p>

      {/* 드롭 존 */}
      <div
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => fileRef.current?.click()}
        className="rounded-2xl p-8 text-center cursor-pointer transition-all"
        style={{
          border: `2px dashed ${dragOver ? "var(--accent)" : "var(--border-default)"}`,
          background: dragOver ? "var(--accent-light)" : "var(--bg-subtle)",
        }}
      >
        {importMutation.isPending ? (
          <div className="flex flex-col items-center gap-2">
            <LoadingSpinner size={24} />
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              가져오는 중...
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <FileText size={28} style={{ color: dragOver ? "var(--accent)" : "var(--text-muted)" }} />
            <p className="text-sm font-medium" style={{ color: "var(--text-secondary)" }}>
              CSV 파일을 드래그하거나 클릭해서 선택
            </p>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>
              북적북적 형식만 지원
            </p>
          </div>
        )}
      </div>

      <input
        ref={fileRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
          e.target.value = "";
        }}
      />

      {/* 결과 */}
      {result && (
        <div
          className="rounded-xl p-4 flex flex-col gap-2 animate-fade-in"
          style={{
            background: result.created > 0 ? "var(--status-read-bg)" : "var(--bg-subtle)",
            border: `1px solid ${result.created > 0 ? "var(--status-read)" : "var(--border-default)"}`,
          }}
        >
          <div className="flex items-center gap-2">
            {result.created > 0 ? (
              <CheckCircle size={16} style={{ color: "var(--status-read)" }} />
            ) : (
              <AlertCircle size={16} style={{ color: "var(--text-muted)" }} />
            )}
            <p
              className="text-sm font-semibold"
              style={{ color: result.created > 0 ? "var(--status-read)" : "var(--text-muted)" }}
            >
              {result.created > 0
                ? `${result.created}권이 서재에 추가됐어요!`
                : "새로 추가된 책이 없어요"}
            </p>
          </div>
          <div className="flex gap-3 text-xs" style={{ color: "var(--text-secondary)" }}>
            <span>전체: {result.total}권</span>
            <span>추가됨: {result.created}권</span>
            <span>건너뜀: {result.skipped}권</span>
            {result.failed > 0 && <span style={{ color: "#EF4444" }}>실패: {result.failed}권</span>}
          </div>
          {result.errors.length > 0 && (
            <div className="flex flex-col gap-1">
              {result.errors.slice(0, 3).map((err, i) => (
                <p key={i} className="text-xs" style={{ color: "#EF4444" }}>
                  {err}
                </p>
              ))}
              {result.errors.length > 3 && (
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  외 {result.errors.length - 3}개의 오류
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** 계정 관리 섹션 (계정 삭제) */
function AccountManagement() {
  const { logout } = useAuth();
  const [showConfirm, setShowConfirm] = useState(false);
  const [inputText, setInputText] = useState("");

  const deleteMutation = useMutation({
    mutationFn: deleteAccount,
    onSuccess: () => {
      logout();
    },
  });

  const handleOpenConfirm = () => {
    setInputText("");
    setShowConfirm(true);
  };

  const handleClose = () => {
    setShowConfirm(false);
    setInputText("");
  };

  const CONFIRM_TEXT = "계정 삭제";
  const isConfirmed = inputText === CONFIRM_TEXT;

  return (
    <>
      <div
        className="card p-5 flex flex-col gap-4"
        style={{ border: "1px solid #FEE2E2" }}
      >
        <div className="flex items-center gap-2">
          <AlertTriangle size={16} style={{ color: "#EF4444" }} />
          <h2 className="text-sm font-bold" style={{ color: "#EF4444" }}>
            계정 관리
          </h2>
        </div>

        <div
          className="rounded-xl p-4"
          style={{ background: "#FEF2F2" }}
        >
          <p className="text-xs leading-relaxed" style={{ color: "#7F1D1D" }}>
            계정을 삭제하면 서재, 독서 기록, 메모, 하이라이트 등
            <strong> 모든 데이터가 영구적으로 삭제</strong>됩니다.
            이 작업은 되돌릴 수 없습니다.
          </p>
        </div>

        <div className="flex justify-end">
          <button
            type="button"
            onClick={handleOpenConfirm}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-colors cursor-pointer"
            style={{ background: "#FEF2F2", color: "#EF4444", border: "1px solid #FECACA" }}
          >
            <Trash2 size={14} />
            계정 삭제
          </button>
        </div>
      </div>

      {/* 2단계 확인 다이얼로그 */}
      {showConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: "rgba(28, 25, 23, 0.6)", backdropFilter: "blur(4px)" }}
        >
          <div
            className="w-full max-w-sm rounded-3xl overflow-hidden animate-fade-in"
            style={{
              background: "var(--bg-card)",
              boxShadow: "var(--shadow-lg)",
              border: "1.5px solid #FECACA",
            }}
          >
            {/* 다이얼로그 헤더 */}
            <div
              className="flex items-center justify-between px-5 py-4"
              style={{ borderBottom: "1px solid var(--border-default)" }}
            >
              <div className="flex items-center gap-2">
                <AlertTriangle size={18} style={{ color: "#EF4444" }} />
                <h3 className="text-sm font-bold" style={{ color: "#EF4444" }}>
                  계정 삭제 확인
                </h3>
              </div>
              <button
                type="button"
                onClick={handleClose}
                disabled={deleteMutation.isPending}
                className="p-1.5 rounded-xl transition-colors cursor-pointer"
                style={{ color: "var(--text-muted)" }}
              >
                <X size={18} />
              </button>
            </div>

            {/* 다이얼로그 내용 */}
            <div className="p-5 flex flex-col gap-4">
              <div
                className="rounded-xl p-4"
                style={{ background: "#FEF2F2", border: "1px solid #FECACA" }}
              >
                <p className="text-xs leading-relaxed" style={{ color: "#7F1D1D" }}>
                  이 작업은 <strong>되돌릴 수 없습니다.</strong><br />
                  서재, 독서 기록, 메모, 하이라이트, 추천 기록 등
                  모든 데이터가 영구적으로 삭제됩니다.
                </p>
              </div>

              <div className="flex flex-col gap-2">
                <label
                  className="text-xs font-semibold"
                  style={{ color: "var(--text-secondary)" }}
                >
                  계속하려면 아래에 <strong style={{ color: "#EF4444" }}>"{CONFIRM_TEXT}"</strong>를 입력하세요
                </label>
                <input
                  type="text"
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  placeholder={CONFIRM_TEXT}
                  disabled={deleteMutation.isPending}
                  className="w-full px-4 py-2.5 rounded-xl text-sm"
                  style={{
                    background: "var(--bg-subtle)",
                    border: `1px solid ${isConfirmed ? "#EF4444" : "var(--border-default)"}`,
                    color: "var(--text-primary)",
                    outline: "none",
                  }}
                />
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleClose}
                  disabled={deleteMutation.isPending}
                  className="flex-1 py-2.5 rounded-xl text-sm font-medium transition-colors cursor-pointer"
                  style={{
                    background: "var(--bg-subtle)",
                    color: "var(--text-secondary)",
                    border: "1px solid var(--border-default)",
                  }}
                >
                  취소
                </button>
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate()}
                  disabled={!isConfirmed || deleteMutation.isPending}
                  className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-sm font-semibold transition-all cursor-pointer"
                  style={{
                    background: isConfirmed ? "#EF4444" : "var(--bg-subtle)",
                    color: isConfirmed ? "white" : "var(--text-muted)",
                    border: "none",
                    opacity: !isConfirmed || deleteMutation.isPending ? 0.6 : 1,
                    cursor: !isConfirmed || deleteMutation.isPending ? "not-allowed" : "pointer",
                  }}
                >
                  {deleteMutation.isPending ? (
                    <LoadingSpinner size={14} />
                  ) : (
                    <Trash2 size={14} />
                  )}
                  삭제하기
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
