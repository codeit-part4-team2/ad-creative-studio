"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/components/providers/auth-provider";

const NAV_ITEMS = [
  { href: "/", label: "DASHBOARD" },
  { href: "/create", label: "CREATE" },
  { href: "/history", label: "HISTORY" },
  { href: "/publishing", label: "PUBLISH" },
  { href: "/community", label: "COMMUNITY" },
];

export function TopNav() {
  const pathname = usePathname();
  const { customer, logout } = useAuth();

  return (
    <header className="flex h-16 items-center justify-between border-b border-border bg-card px-8">
      <div className="flex items-center gap-10">
        <span className="text-lg font-bold tracking-tight">AD STUDIO</span>
        <nav className="flex items-center gap-6">
          {NAV_ITEMS.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "text-xs font-medium tracking-wide transition-colors",
                  active ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
      {customer ? (
        <button
          onClick={() => logout()}
          className="font-mono text-xs text-muted-foreground hover:text-foreground"
          title="로그아웃"
        >
          {customer.company_name} · {customer.customer_id}
        </button>
      ) : (
        <span className="font-mono text-xs text-muted-foreground">ACCOUNT</span>
      )}
    </header>
  );
}
