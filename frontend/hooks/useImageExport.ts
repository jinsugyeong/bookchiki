"use client";

import { useCallback, useState } from "react";

interface UseImageExportOptions {
  filename?: string;
  scale?: number;
}

/**
 * html2canvas를 이용해 DOM 요소를 PNG로 내보내는 훅.
 * Dynamic import로 SSR 회피.
 */
export function useImageExport() {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const exportToPng = useCallback(
    async (element: HTMLElement | null, options: UseImageExportOptions = {}) => {
      if (!element) return;

      const { filename = "bookchiki-image.png", scale = 2 } = options;

      setIsExporting(true);
      setError(null);

      try {
        // SSR 방지 — dynamic import
        const html2canvas = (await import("html2canvas")).default;

        const canvas = await html2canvas(element, {
          scale,
          useCORS: true,
          allowTaint: false,
          backgroundColor: null,
          logging: false,
          // 웹폰트 로드 대기
          onclone: (_doc: Document, cloned: HTMLElement) => {
            cloned.style.fontFamily = element.style.fontFamily;
          },
        });

        const dataUrl = canvas.toDataURL("image/png", 1.0);
        const link = document.createElement("a");
        link.href = dataUrl;
        link.download = filename;
        link.click();
      } catch (err) {
        console.error("[useImageExport] 이미지 내보내기 실패:", err);
        setError("이미지 생성에 실패했어요. 다시 시도해주세요.");
      } finally {
        setIsExporting(false);
      }
    },
    []
  );

  return { exportToPng, isExporting, error };
}
