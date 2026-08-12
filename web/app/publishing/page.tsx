import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export default function PublishingPage() {
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
            백엔드의 사람 승인·YouTube 예약 경계는 준비됐습니다. 이 화면의 발음 확인,
            예약 시각 입력, 승인·거절 제어와 실제 팀 채널 OAuth 검증은 아직 남아 있습니다.
            그 전까지 업로드는 기본 비활성 상태입니다.
          </CardDescription>
        </CardHeader>
      </Card>
    </div>
  );
}
