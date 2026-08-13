"use client";

import { useState } from "react";
import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api/client";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { customer, isLoading } = useAuth();

  if (isLoading) return null;
  if (!customer) return <LoginForm />;
  return <>{children}</>;
}

function LoginForm() {
  const { login } = useAuth();
  const [customerId, setCustomerId] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(customerId, pin);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "로그인에 실패했습니다");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-sm flex-col justify-center px-8 py-24">
      <p className="text-xs font-semibold tracking-wide text-muted-foreground">CLIENT LOGIN</p>
      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        <div className="space-y-2">
          <Label htmlFor="customer_id">Customer ID</Label>
          <Input
            id="customer_id"
            placeholder="CUS-0001"
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="pin">PIN</Label>
          <Input
            id="pin"
            type="password"
            value={pin}
            onChange={(e) => setPin(e.target.value)}
          />
        </div>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" variant="accent" className="w-full" disabled={submitting}>
          {submitting ? "확인 중..." : "ACCESS STUDIO"}
        </Button>
      </form>
    </div>
  );
}
