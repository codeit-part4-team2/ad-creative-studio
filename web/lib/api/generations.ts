import { apiFetch } from "./client";
import type { GenerationResultResponse, JobStatusResponse, TimeSlot } from "@/lib/types/api";

export async function createGeneration(input: {
  productId: string;
  timeSlots: TimeSlot[];
}): Promise<{ job_id: string; status: string }> {
  return apiFetch("/api/v1/generations", {
    method: "POST",
    body: JSON.stringify({ product_id: input.productId, time_slots: input.timeSlots }),
  });
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  return apiFetch(`/api/v1/jobs/${jobId}`);
}

export async function getGenerationResult(jobId: string): Promise<GenerationResultResponse> {
  return apiFetch(`/api/v1/generations/${jobId}`);
}
