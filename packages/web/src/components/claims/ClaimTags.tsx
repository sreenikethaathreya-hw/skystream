import { Badge } from "@/components/ui/badge";
import { ProbBar } from "@/components/ui/prob-bar";
import { humanize } from "@/lib/format";
import type { DecisionAnswer } from "@/lib/types";

const TAGS: { key: string; label: string }[] = [
  { key: "driver", label: "Driver" },
  { key: "direction", label: "Direction" },
  { key: "magnitude", label: "Size" },
  { key: "competitor", label: "Competitor" },
  { key: "variety", label: "Variety" },
  { key: "evidence_source", label: "Evidence" },
  { key: "specificity", label: "Specificity" },
  { key: "verifiable", label: "Checkable" },
  { key: "consistent_with_market_notes", label: "Fits market notes" },
  { key: "addresses_flags", label: "Explains flags" },
];

const SCORE_LABELS: Record<string, string[]> = {
  magnitude: ["Negligible", "Small", "Moderate", "Large"],
  specificity: ["Vague", "Some detail", "Specific", "Quantified"],
};

function describe(key: string, answer: DecisionAnswer): { text: string; p: number } {
  if (answer.type === "choice") {
    return { text: humanize(answer.choice ?? "none"), p: answer.confidence ?? 0 };
  }
  if (answer.type === "score") {
    const labels = SCORE_LABELS[key] ?? [];
    const level = Math.round(answer.score ?? 0);
    return { text: labels[level] ?? (answer.score ?? 0).toFixed(1), p: answer.confidence ?? 0 };
  }
  const p = answer.noul ?? 0;
  return { text: p >= 0.5 ? "Yes" : "No", p: p >= 0.5 ? p : 1 - p };
}

export function ClaimTags({
  decisions,
  provider,
  latencyMs,
  compact = false,
}: {
  decisions: Record<string, DecisionAnswer>;
  provider: string;
  latencyMs?: number;
  compact?: boolean;
}) {
  const present = TAGS.filter((t) => decisions[t.key]);
  return (
    <div data-testid="claim-tags">
      <div className={compact ? "flex flex-wrap gap-1.5" : "grid grid-cols-2 gap-2 lg:grid-cols-5"}>
        {present.map(({ key, label }) => {
          const { text, p } = describe(key, decisions[key]);
          if (compact) {
            return (
              <Badge key={key} tone="jev" title={`${label}: ${Math.round(p * 100)}%`}>
                {label}: {text}
              </Badge>
            );
          }
          return (
            <div key={key} className="rounded-lg border border-jev/20 bg-jev-50 px-2.5 py-1.5">
              <p className="text-[10px] font-medium uppercase tracking-wide text-jev/80">{label}</p>
              <p className="text-sm font-medium text-ink">{text}</p>
              <ProbBar value={p} className="mt-1" />
              <p className="tabular mt-0.5 text-[10px] text-muted">{Math.round(p * 100)}% probability</p>
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-[11px] text-muted">
        Decided by <span className="font-medium text-jev">{provider}</span>
        {latencyMs !== undefined && ` in ${latencyMs} ms`}. Jev returns typed decisions with probabilities; it never
        writes or changes the number.
      </p>
    </div>
  );
}
