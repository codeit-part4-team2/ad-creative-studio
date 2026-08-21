import { apiFetch } from "./client";
import type {
  GenerationResultResponse,
  JobStatusResponse,
  OutputFormat,
  TimeSlot,
} from "@/lib/types/api";

export async function createGeneration(input: {
  productId: string;
  timeSlots: TimeSlot[];
  outputFormats: OutputFormat[];
}): Promise<{ job_id: string; status: string }> {
  return apiFetch("/api/v1/generations", {
    method: "POST",
    body: JSON.stringify({
      product_id: input.productId,
      time_slots: input.timeSlots,
      output_formats: input.outputFormats,
    }),
  });
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  return apiFetch(`/api/v1/jobs/${jobId}`);
}

export async function getGenerationResult(
  jobId: string,
): Promise<GenerationResultResponse> {
  return apiFetch(`/api/v1/generations/${jobId}`);
}

export async function updateGenerationCopy(
  jobId: string,
  input: {
    resultId: string;
    headline: string;
    subcopy: string;
  },
): Promise<{
  job_id: string;
  result_id: string;
  headline: string;
  subcopy: string;
}> {
  return apiFetch(`/api/v1/generations/${jobId}/copy`, {
    method: "PATCH",
    body: JSON.stringify({
      result_id: input.resultId,
      headline: input.headline,
      subcopy: input.subcopy,
    }),
  });
}
