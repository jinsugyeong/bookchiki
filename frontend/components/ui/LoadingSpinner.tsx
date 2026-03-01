/** 로딩 스피너 */
export default function LoadingSpinner({ size = 24 }: { size?: number }) {
  return (
    <div
      className="inline-block rounded-full animate-spin"
      style={{
        width: size,
        height: size,
        border: `2px solid var(--border-default)`,
        borderTopColor: "var(--accent)",
      }}
      role="status"
      aria-label="로딩 중"
    />
  );
}

/** 전체 화면 로딩 */
export function PageLoading() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-24">
      <LoadingSpinner size={32} />
      <p className="text-sm" style={{ color: "var(--text-muted)" }}>
        불러오는 중...
      </p>
    </div>
  );
}

/** 스켈레톤 카드 */
export function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div
      className={`rounded-2xl overflow-hidden animate-pulse-subtle ${className}`}
      style={{ background: "var(--bg-subtle)", border: "1px solid var(--border-default)" }}
    >
      <div style={{ height: "140px", background: "var(--border-default)" }} />
      <div className="p-4 flex flex-col gap-2">
        <div
          className="rounded"
          style={{ height: "14px", width: "75%", background: "var(--border-default)" }}
        />
        <div
          className="rounded"
          style={{ height: "12px", width: "50%", background: "var(--border-default)" }}
        />
      </div>
    </div>
  );
}
