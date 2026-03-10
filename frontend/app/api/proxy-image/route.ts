import { NextRequest, NextResponse } from "next/server";

/**
 * 외부 이미지 CORS 프록시 — html2canvas가 크로스 오리진 이미지를 캡처할 수 있도록 서버에서 중계.
 * 사용법: /api/proxy-image?url=https://...
 */
export async function GET(request: NextRequest) {
  const url = request.nextUrl.searchParams.get("url");

  if (!url) {
    return new NextResponse("url 파라미터가 필요합니다.", { status: 400 });
  }

  // 허용된 도메인만 프록시 (보안)
  const allowedHosts = [
    "image.aladin.co.kr",
    "cover.nl.go.kr",
    "lh3.googleusercontent.com",
    // DALL-E 3 이미지 (Azure Blob Storage)
    "blob.core.windows.net",
    "oaidalleapiprodscus.blob.core.windows.net",
    "dalleproduse.blob.core.windows.net",
  ];

  let parsedUrl: URL;
  try {
    parsedUrl = new URL(url);
  } catch {
    return new NextResponse("유효하지 않은 URL입니다.", { status: 400 });
  }

  if (!allowedHosts.some((host) => parsedUrl.hostname.endsWith(host))) {
    return new NextResponse("허용되지 않은 이미지 도메인입니다.", { status: 403 });
  }

  try {
    const response = await fetch(url, {
      headers: { "User-Agent": "Mozilla/5.0" },
    });

    if (!response.ok) {
      return new NextResponse("이미지를 가져오는 데 실패했습니다.", { status: response.status });
    }

    const buffer = await response.arrayBuffer();
    const contentType = response.headers.get("content-type") || "image/jpeg";

    return new NextResponse(buffer, {
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=86400",
        "Access-Control-Allow-Origin": "*",
      },
    });
  } catch {
    return new NextResponse("이미지 프록시 요청 실패", { status: 500 });
  }
}
