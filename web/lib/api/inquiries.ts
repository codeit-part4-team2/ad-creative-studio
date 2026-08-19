import { apiFetch } from "./client";

export type InquiryStatus = "waiting" | "answered";

export type Inquiry = {
  inquiry_id: string;
  customer_id: string;
  company_name: string;
  title: string;
  content: string;
  status: InquiryStatus;
  answer: string | null;
  answered_at: number | null;
  created_at: number;
};

export type InquiryCreate = {
  title: string;
  content: string;
};

export async function getInquiries(): Promise<Inquiry[]> {
  return apiFetch("/api/v1/inquiries");
}

export async function getInquiry(inquiryId: string): Promise<Inquiry> {
  return apiFetch(`/api/v1/inquiries/${inquiryId}`);
}

export async function createInquiry(input: InquiryCreate): Promise<Inquiry> {
  return apiFetch("/api/v1/inquiries", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
