"use client";

import { usePathname } from "next/navigation";
import Header from "./Header";

const NO_HEADER_PATHS = ["/login", "/auth/callback"];

export default function ConditionalLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const hideHeader = NO_HEADER_PATHS.some((p) => pathname.startsWith(p));

  return (
    <>
      {!hideHeader && <Header />}
      {hideHeader ? (
        children
      ) : (
        <main className="max-w-6xl mx-auto px-4 py-6">{children}</main>
      )}
    </>
  );
}
