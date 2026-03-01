"use client";

import { useState } from "react";
import { Star } from "lucide-react";

interface StarRatingProps {
  value?: number | null;
  onChange?: (rating: number) => void;
  readonly?: boolean;
  size?: number;
}

/** 별점 컴포넌트 (읽기/쓰기 모드) */
export default function StarRating({
  value = 0,
  onChange,
  readonly = false,
  size = 16,
}: StarRatingProps) {
  const [hovered, setHovered] = useState(0);
  const displayValue = readonly ? (value ?? 0) : (hovered || value || 0);

  return (
    <div className="flex items-center gap-0.5" role="group" aria-label="별점">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          onClick={() => !readonly && onChange?.(star)}
          onMouseEnter={() => !readonly && setHovered(star)}
          onMouseLeave={() => !readonly && setHovered(0)}
          disabled={readonly}
          className={`transition-transform duration-100 ${
            readonly ? "cursor-default" : "cursor-pointer hover:scale-110"
          }`}
          aria-label={`${star}점`}
        >
          <Star
            size={size}
            fill={star <= displayValue ? "var(--star)" : "none"}
            color={star <= displayValue ? "var(--star)" : "var(--border-default)"}
            strokeWidth={1.5}
          />
        </button>
      ))}
    </div>
  );
}
