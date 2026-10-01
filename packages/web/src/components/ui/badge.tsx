import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export type Tone = "neutral" | "brand" | "warn" | "crit" | "info" | "jev";

const tones: Record<Tone, string> = {
  neutral: "bg-canvas text-muted border-line",
  brand: "bg-brand-50 text-brand-700 border-brand-100",
  warn: "bg-warn-50 text-warn-700 border-warn-500/30",
  crit: "bg-crit-50 text-crit-700 border-crit-500/30",
  info: "bg-info-50 text-info-700 border-info-500/30",
  jev: "bg-jev-50 text-jev border-jev/30",
};

export function Badge({ tone = "neutral", className, ...props }: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}

const STATUS_TONES: Record<string, Tone> = {
  submitted: "info",
  needs_justification: "warn",
  approved: "brand",
  discuss: "warn",
  challenged: "crit",
  superseded: "neutral",
  confirmed: "brand",
  contradicted: "crit",
  inconclusive: "warn",
  pending: "neutral",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={STATUS_TONES[status] ?? "neutral"}>{status.replace(/_/g, " ")}</Badge>;
}
