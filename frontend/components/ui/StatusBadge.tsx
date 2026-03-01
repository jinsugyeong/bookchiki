import { BookOpen, CheckCircle, Heart } from "lucide-react";

type Status = "read" | "reading" | "wishlist";

const STATUS_CONFIG: Record<
  Status,
  { label: string; bg: string; color: string; Icon: typeof BookOpen }
> = {
  read: {
    label: "읽은 책",
    bg: "var(--status-read-bg)",
    color: "var(--status-read)",
    Icon: CheckCircle,
  },
  reading: {
    label: "읽고 있는 책",
    bg: "var(--status-reading-bg)",
    color: "var(--status-reading)",
    Icon: BookOpen,
  },
  wishlist: {
    label: "읽고 싶은 책",
    bg: "var(--status-wishlist-bg)",
    color: "var(--status-wishlist)",
    Icon: Heart,
  },
};

/** 독서 상태 배지 */
export default function StatusBadge({ status }: { status: Status }) {
  const { label, bg, color, Icon } = STATUS_CONFIG[status];
  return (
    <span
      className="badge flex-shrink-0 whitespace-nowrap"
      style={{ background: bg, color }}
    >
      <Icon size={11} strokeWidth={2.5} />
      {label}
    </span>
  );
}
