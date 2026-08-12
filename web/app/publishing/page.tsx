"use client";

import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { RequireAuth } from "@/components/auth/require-auth";

function PublishingContent() {
  return (
    <div className="mx-auto max-w-2xl space-y-6 px-8 py-10">
      <div>
        <h1 className="text-2xl font-semibold">게시 관리</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          완성된 쇼츠를 검토하고 YouTube에 예약·즉시 게시합니다.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>준비 중입니다</CardTitle>
          <CardDescription>
            YouTube 예약 게시는 이미지·쇼츠 E2E 검증이 끝난 뒤 착수하기로
            결정된 기능입니다. 백엔드 API(POST /videos/{"{"}video_id{"}"}/publish)와
            OAuth 연동이 아직 준비되지 않았습니다.
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  );
}

export default function PublishingPage() {
  return (
    <RequireAuth>
      <PublishingContent />
    </RequireAuth>
  );
}
