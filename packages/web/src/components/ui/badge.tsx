import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export type Tone = "neutral" | "brand" | "warn" | "crit" | "info" | "jev";

const tones: Record<Tone, string> = {
  neutral: "bg-canvas text-muted",
  brand: "bg-brand-50 text-brand-700",
  warn: "bg-warn-50 text-warn-700",
  crit: "bg-crit-50 text-crit-700",
  info: "bg-info-50 text-info-700",
  jev: "bg-jev-50 text-jev",
};

const dots: Record<Tone, string> = {
  neutral: "bg-muted/50",
  brand: "bg-brand-600",
  warn: "bg-warn-500",
  crit: "bg-crit-500",
  info: "bg-info-500",
  jev: "bg-jev",
};

export function Badge({ tone = "neutral", className, ...props }: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] font-medium",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}

const STATUS_TONES: Record<string, Tone> = {
  submitted: "info",
  approved: "brand",
  discuss: "warn",
  challenged: "crit",
  superseded: "neutral",
  confirmed: "brand",
  contradicted: "crit",
  inconclusive: "warn",
  pending: "neutral",
};

/** Workflow state as a dot and a word, so it never competes with the tags around it. */
export function StatusBadge({ status }: { status: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-[11px] font-medium text-muted">
      <span aria-hidden="true" className={cn("size-1.5 rounded-full", dots[STATUS_TONES[status] ?? "neutral"])} />
      {status}
    </span>
  );
}
