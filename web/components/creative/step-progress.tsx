import { cn } from "@/lib/utils";

const STEPS = ["PRODUCT", "SCHEDULE", "STYLE", "GENERATE", "APPROVE"];

export function StepProgress({ currentIndex }: { currentIndex: number }) {
  return (
    <div className="mb-10 grid grid-cols-5 gap-3">
      {STEPS.map((label, i) => (
        <div key={label} className="space-y-1.5">
          <div
            className={cn(
              "step-line w-full",
              i < currentIndex && "step-line--done",
              i === currentIndex && "step-line--current"
            )}
          />
          <span
            className={cn(
              "text-[11px] font-semibold tracking-wide",
              i <= currentIndex ? "text-foreground" : "text-muted-foreground"
            )}
          >
            {label}
          </span>
        </div>
      ))}
    </div>
  );
}
