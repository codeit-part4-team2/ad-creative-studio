"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StepProgress } from "@/components/creative/step-progress";
import { createProduct } from "@/lib/api/products";
import { createGeneration } from "@/lib/api/generations";
import { TIME_SLOT_OPTIONS, MAX_TIME_SLOTS, TONE_LABEL } from "@/lib/constants";
import type { TimeSlot } from "@/lib/types/api";
import { cn } from "@/lib/utils";
import { Upload } from "lucide-react";

type Step = 1 | 2 | 3; // 1=PRODUCT, 2=SCHEDULE, 3=STYLE+GENERATE(같은 화면)

import { RequireAuth } from "@/components/auth/require-auth";

function CreatePageContent() {
  const router = useRouter();
  const [step, setStep] = useState<Step>(1);

  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [productName, setProductName] = useState("");
  const [price, setPrice] = useState<number>(0);
  const [sellingPoints, setSellingPoints] = useState("");
  const [productId, setProductId] = useState<string | null>(null);
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
    onSuccess: (data) => router.push(`/result/${data.job_id}`),
  });

  function handleImageChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImageFile(file);
    setImagePreview(URL.createObjectURL(file));
  }

  function toggleSlot(slot: TimeSlot) {
    setSelectedSlots((prev) => (prev.includes(slot) ? prev.filter((s) => s !== slot) : [...prev, slot]));
  }

  const productReady = Boolean(imageFile && productName.trim() && price > 0);
  const canGenerate = selectedSlots.length > 0 && selectedSlots.length <= MAX_TIME_SLOTS;

  // 진행바 인덱스: 0=PRODUCT 1=SCHEDULE 2=STYLE 3=GENERATE 4=APPROVE(결과 페이지에서)
  const progressIndex = generationMutation.isPending ? 3 : step === 3 ? 2 : step - 1;

  return (
    <div className="mx-auto w-full max-w-[1440px] px-8 py-8 lg:px-12">
      <section className="rounded-[28px] bg-muted px-8 py-10 lg:px-12">
        <StepProgress currentIndex={progressIndex} />

        <div className="grid gap-10 md:grid-cols-[1fr_1.1fr]">
          {/* 좌측 - 제품 이미지 */}
          <div>
            <label
              htmlFor="image"
              className={cn(
                "flex aspect-square w-full cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-card text-center",
                imagePreview && "cursor-default"
              )}
            >
              {imagePreview ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={imagePreview} alt="제품 미리보기" className="h-full w-full rounded-lg object-cover" />
              ) : (
                <>
                  <Upload className="h-6 w-6 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">제품 사진을 업로드하세요</span>
                </>
              )}
              <input
                id="image"
                type="file"
                accept="image/jpeg,image/png"
                className="hidden"
                disabled={step > 1}
                onChange={handleImageChange}
              />
            </label>
            {productName && (
              <p className="mt-3 text-sm font-medium">
                {productName}
                {price > 0 && <span className="text-muted-foreground"> · {price.toLocaleString()}원</span>}
              </p>
            )}
          </div>

          {/* 우측 - 단계별 폼 */}
          <div className="space-y-8">
            {step === 1 && (
              <div className="space-y-4">
                <p className="text-xs font-semibold tracking-wide text-muted-foreground">PRODUCT INFORMATION</p>
                <div className="space-y-2">
                  <Label htmlFor="name">제품명</Label>
                  <Input id="name" value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="스팀 에어프라이어 5L" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="price">가격</Label>
                  <Input id="price" type="number" min={0} value={price || ""} onChange={(e) => setPrice(Number(e.target.value))} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="selling">특징 (선택, 쉼표로 구분)</Label>
                  <Input id="selling" value={sellingPoints} onChange={(e) => setSellingPoints(e.target.value)} placeholder="기름 없이 조리, 1인 가구 추천" />
                </div>
                {productMutation.isError && (
                  <p className="text-sm text-destructive">{(productMutation.error as Error).message}</p>
                )}
                <Button
                  disabled={!productReady || productMutation.isPending}
                  onClick={() => imageFile && productMutation.mutate({ image: imageFile, productName, price, sellingPoints })}
                >
                  {productMutation.isPending ? "등록 중..." : "NEXT →"}
                </Button>
              </div>
            )}

            {step >= 2 && (
              <div className="space-y-4">
                <p className="text-xs font-semibold tracking-wide text-muted-foreground">TIME SLOT</p>
                <div className="flex flex-wrap gap-2">
                  {TIME_SLOT_OPTIONS.map((opt) => {
                    const active = selectedSlots.includes(opt.value);
                    return (
                      <button
                        key={opt.value}
                        type="button"
                        disabled={step > 2}
                        onClick={() => toggleSlot(opt.value)}
                        className={cn(
                          "rounded-full border px-4 py-2 text-sm transition-colors",
                          active ? "border-foreground bg-foreground text-background" : "border-border bg-card hover:bg-muted"
                        )}
                      >
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
                {selectedSlots.length > MAX_TIME_SLOTS && (
                  <p className="text-sm text-destructive">최대 {MAX_TIME_SLOTS}개까지만 선택할 수 있어요.</p>
                )}
                {step === 2 && (
                  <Button disabled={!canGenerate} onClick={() => setStep(3)}>
                    NEXT →
                  </Button>
                )}
              </div>
            )}

            {step === 3 && (
              <div className="space-y-4">
                <p className="text-xs font-semibold tracking-wide text-muted-foreground">AD STYLE</p>
                <p className="text-sm text-muted-foreground">
                  톤 4종이 모두 자동으로 생성됩니다 — 결과에서 마음에 드는 걸 고르시면 됩니다.
                </p>
                <div className="flex flex-wrap gap-2">
                  {Object.values(TONE_LABEL).map((label) => (
                    <span key={label} className="rounded-full border border-border bg-card px-4 py-2 text-sm text-muted-foreground">
                      {label}
                    </span>
                  ))}
                </div>

                <div className="rounded-lg border border-border bg-card p-5">
                  <p className="text-base font-semibold">READY TO GENERATE</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    톤 4종 × 시간대 {selectedSlots.length}개 × 기본 규격 2종 = {selectedSlots.length * 8}개 이미지를 생성합니다.
                  </p>
                  {generationMutation.isError && (
                    <p className="mt-2 text-sm text-destructive">{(generationMutation.error as Error).message}</p>
                  )}
                  <Button
                    variant="accent"
                    className="mt-4"
                    disabled={generationMutation.isPending || !productId}
                    onClick={() => productId && generationMutation.mutate({ productId, timeSlots: selectedSlots })}
                  >
                    {generationMutation.isPending ? "생성 요청 중..." : "GENERATE NOW →"}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

export default function CreatePage() {
  return (
    <RequireAuth>
      <CreatePageContent />
    </RequireAuth>
  );
}
