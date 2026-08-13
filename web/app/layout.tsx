import type { Metadata } from "next";
import "pretendard/dist/web/variable/pretendardvariable.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./globals.css";
import { QueryProvider } from "@/components/providers/query-provider";
import { AuthProvider } from "@/components/providers/auth-provider";
import { TopNav } from "@/components/layout/top-nav";

export const metadata: Metadata = {
  title: "AD STUDIO — 소형가전 광고 생성기",
  description: "제품 사진 한 장으로 톤 4종 광고 이미지·쇼츠를 만드는 서비스",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full">
        <QueryProvider>
          <AuthProvider>
            <div className="flex min-h-screen flex-col">
              <TopNav />
              <main className="flex-1 overflow-y-auto">{children}</main>
            </div>
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
