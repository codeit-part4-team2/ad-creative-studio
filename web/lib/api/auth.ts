import { apiFetch } from "./client";

export interface Customer {
  customer_id: string;
  company_name: string;
  status: string;
  plan: string;
}

export interface LoginResponse {
  token: string;
  customer: Customer;
}

export async function login(customerId: string, pin: string): Promise<LoginResponse> {
  return apiFetch("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ customer_id: customerId, pin }),
  });
}

export async function logout(): Promise<void> {
  return apiFetch("/api/v1/auth/logout", { method: "POST" });
}

export async function me(): Promise<Customer> {
  return apiFetch("/api/v1/auth/me");
}
