"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { createProduct } from "@/lib/api/products";
import { createGeneration } from "@/lib/api/generations";
import { TIME_SLOT_OPTIONS, MAX_TIME_SLOTS, TONE_LABEL } from "@/lib/constants";
import type { TimeSlot } from "@/lib/types/api";

type Step = 1 | 2 | 3;

export default function CreatePage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>(1);

  // ① 상품 정보
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [productName, setProductName] = useState("");
  const [price, setPrice] = useState<number>(0);
  const [sellingPoints, setSellingPoints] = useState("");
  const [productId, setProductId] = useState<string | null>(null);

  // ② 광고 설정
  const [selectedSlots, setSelectedSlots] = useState<TimeSlot[]>([]);

  const productMutation = useMutation({
    mutationFn: createProduct,
    onSuccess: (data) => {
      setProductId(data.product_id);
      setStep(2);
    },
  });

  const generationMutation = useMutation({
    mutationFn: createGeneration,
    onSuccess: (data) => {
      router.push(`/result/${data.job_id}`);
    },
  });

  function handleImageChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageFile(file);
    setImagePreview(URL.createObjectURL(file));
  }

  function toggleSlot(slot: TimeSlot) {
    setSelectedSlots((prev) =>
      prev.includes(slot) ? prev.filter((s) => s !== slot) : [...prev, slot]
    );
  }

  const productReady = Boolean(imageFile && productName.trim() && price > 0);
  const canGenerate = selectedSlots.length > 0 && selectedSlots.length <= MAX_TIME_SLOTS;

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-8 py-10">
      <div>
        <h1 className="text-2xl font-semibold">광고 만들기</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          제품 사진 한 장이면, 톤 4종 광고 이미지 세트가 만들어집니다.
        </p>
      </div>

      {/* ① 상품 정보 */}
      <Card className={step > 1 ? "opacity-70" : ""}>
        <CardHeader>
          <CardTitle>① 상품 정보</CardTitle>
          {step > 1 && productId && (
            <CardDescription className="font-mono text-xs">product_id: {productId}</CardDescription>
          )}
        </CardHeader>
        {step === 1 && (
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="image">제품 사진 *</Label>
              <Input id="image" type="file" accept="image/jpeg,image/png" onChange={handleImageChange} />
              {imagePreview && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={imagePreview} alt="미리보기" className="mt-2 h-40 w-40 rounded-md object-cover border border-border" />
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">제품명 *</Label>
              <Input id="name" value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="스팀 에어프라이어 5L" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="price">가격 *</Label>
              <Input id="price" type="number" min={0} value={price || ""} onChange={(e) => setPrice(Number(e.target.value))} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="selling">셀링포인트 (선택, 쉼표로 구분)</Label>
              <Input id="selling" value={sellingPoints} onChange={(e) => setSellingPoints(e.target.value)} placeholder="기름 없이 조리, 1인 가구 추천" />
            </div>
            {productMutation.isError && (
              <p className="text-sm text-destructive">{(productMutation.error as Error).message}</p>
            )}
            <Button
              disabled={!productReady || productMutation.isPending}
              onClick={() =>
                imageFile &&
                productMutation.mutate({ image: imageFile, productName, price, sellingPoints })
              }
            >
              {productMutation.isPending ? "등록 중..." : "다음: 광고 설정"}
            </Button>
          </CardContent>
        )}
      </Card>

      {/* ② 광고 설정 */}
      {step >= 2 && (
        <Card>
          <CardHeader>
            <CardTitle>② 광고 설정</CardTitle>
            <CardDescription>
              노출 시간대를 최대 {MAX_TIME_SLOTS}개까지 선택하세요. 톤 4종({Object.values(TONE_LABEL).join("·")})은 자동 생성됩니다.
            </CardDescription>
          </CardHeader>
          {step === 2 && (
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                {TIME_SLOT_OPTIONS.map((opt) => (
                  <label
                    key={opt.value}
                    className="flex items-center gap-2 rounded-md border border-border p-3 text-sm hover:bg-muted"
                  >
                    <Checkbox
                      checked={selectedSlots.includes(opt.value)}
                      onCheckedChange={() => toggleSlot(opt.value)}
                    />
                    <span>{opt.label}</span>
                  </label>
                ))}
              </div>
              {selectedSlots.length > MAX_TIME_SLOTS && (
                <p className="text-sm text-destructive">최대 {MAX_TIME_SLOTS}개까지만 선택할 수 있어요.</p>
              )}
              <Button disabled={!canGenerate} onClick={() => setStep(3)}>
                다음: 검토 및 생성
              </Button>
            </CardContent>
          )}
        </Card>
      )}

      {/* ③ 검토 및 생성 */}
      {step === 3 && productId && (
        <Card>
          <CardHeader>
            <CardTitle>③ 검토 및 생성</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm">
              <span className="text-muted-foreground">상품:</span> {productName}
            </p>
            <p className="text-sm">
              <span className="text-muted-foreground">시간대:</span>{" "}
              {selectedSlots.map((s) => TIME_SLOT_OPTIONS.find((o) => o.value === s)?.label).join(", ")}
            </p>
            <p className="text-sm">
              <span className="text-muted-foreground">생성 개수:</span> 톤 4종 × 시간대 {selectedSlots.length}개 ={" "}
              {selectedSlots.length * 4}개 (규격 3종씩)
            </p>
            {generationMutation.isError && (
              <p className="text-sm text-destructive">{(generationMutation.error as Error).message}</p>
            )}
            <Button
              disabled={generationMutation.isPending}
              onClick={() => generationMutation.mutate({ productId, timeSlots: selectedSlots })}
            >
              {generationMutation.isPending ? "요청 중..." : "🎨 광고 생성"}
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
