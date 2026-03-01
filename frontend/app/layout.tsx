import type { Metadata } from "next";
import "./globals.css";
import QueryProvider from "@/components/providers/QueryProvider";
import { AuthProvider } from "@/contexts/AuthContext";
import ConditionalLayout from "@/components/layout/ConditionalLayout";

export const metadata: Metadata = {
  title: "북치기박치기 | AI 독서 기록 & 추천",
  description: "나만의 독서 기록을 관리하고, AI가 딱 맞는 책을 추천해드려요.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>
        <QueryProvider>
          <AuthProvider>
            <ConditionalLayout>{children}</ConditionalLayout>
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
