"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { getHistory } from "@/lib/api/history";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PackagePlus } from "lucide-react";

export default function DashboardPage() {
  const historyQuery = useQuery({ queryKey: ["history", false], queryFn: () => getHistory(false) });

  const totalJobs = historyQuery.data?.length ?? 0;
  const favoriteCount = historyQuery.data?.filter((h) => h.favorite).length ?? 0;

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-8 py-10">
      <div>
        <h1 className="text-2xl font-semibold">대시보드</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          제품 사진 한 장으로 시간대·톤에 맞는 광고 세트를 만드는 서비스입니다.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardDescription>총 생성 건수</CardDescription>
            <CardTitle className="font-mono text-3xl">{totalJobs}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>즐겨찾기</CardDescription>
            <CardTitle className="font-mono text-3xl">{favoriteCount}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="flex flex-col justify-between">
          <CardHeader>
            <CardDescription>새 광고</CardDescription>
            <CardTitle>지금 시작하기</CardTitle>
          </CardHeader>
          <CardContent>
            <Button asChild className="w-full">
              <Link href="/create">
                <PackagePlus /> 광고 만들기
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
