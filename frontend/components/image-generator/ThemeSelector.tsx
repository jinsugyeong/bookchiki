"use client";

import type { Theme } from "./themes";

interface ThemeSelectorProps {
  themes: Theme[];
  selectedId: string;
  onSelect: (theme: Theme) => void;
}

/** 무드 테마 그리드 선택기 */
export default function ThemeSelector({ themes, selectedId, onSelect }: ThemeSelectorProps) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {themes.map((theme) => {
        const isSelected = theme.id === selectedId;
        return (
          <button
            key={theme.id}
            type="button"
            onClick={() => onSelect(theme)}
            className="flex flex-col items-center gap-1.5 cursor-pointer group"
          >
            {/* 컬러 미리보기 */}
            <div
              style={{
                width: "100%",
                aspectRatio: "1",
                borderRadius: "10px",
                background: theme.background,
                border: isSelected ? "2.5px solid var(--accent)" : "2px solid transparent",
                boxShadow: isSelected
                  ? "0 0 0 2px var(--accent-light)"
                  : "0 1px 4px rgba(0,0,0,0.1)",
                transition: "all 0.15s ease",
              }}
            />
            <span
              className="text-[10px] font-medium text-center"
              style={{
                color: isSelected ? "var(--accent-dark)" : "var(--text-secondary)",
                transition: "color 0.15s",
              }}
            >
              {theme.name}
            </span>
          </button>
        );
      })}
    </div>
  );
}
