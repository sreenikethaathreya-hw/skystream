import { cn } from "@/lib/utils";

export function ProbBar({ value, className, tone = "jev" }: { value: number; className?: string; tone?: "jev" | "brand" | "warn" | "crit" }) {
  const color = { jev: "bg-jev", brand: "bg-brand-500", warn: "bg-warn-500", crit: "bg-crit-500" }[tone];
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-line", className)}>
      <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
    </div>
  );
}
