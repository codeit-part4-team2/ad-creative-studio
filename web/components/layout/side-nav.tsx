"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGrid, PackagePlus, History, Send } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/", label: "대시보드", icon: LayoutGrid },
  { href: "/create", label: "광고 만들기", icon: PackagePlus },
  { href: "/history", label: "생성 이력", icon: History },
  { href: "/publishing", label: "게시 관리", icon: Send },
];

export function SideNav() {
  const pathname = usePathname();

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-[var(--ink)] px-3 py-6">
      <div className="mb-8 px-3">
        <p className="font-mono text-xs tracking-widest text-[var(--copper)]">AD STUDIO</p>
        <p className="mt-1 text-sm text-muted-foreground">소형가전 광고 생성기</p>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-[var(--copper)]/15 text-[var(--copper-soft)]"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
