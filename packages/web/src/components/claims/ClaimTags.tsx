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

// A yes/no probability this close to a coin flip is shown as Uncertain rather than a verdict.
const UNCERTAIN_LOW = 0.4;
const UNCERTAIN_HIGH = 0.6;

interface Described {
  text: string;
  p: number;
  uncertain?: boolean;
}

function describe(key: string, answer: DecisionAnswer): Described {
  if (answer.type === "choice") {
    return { text: humanize(answer.choice ?? "none"), p: answer.confidence ?? 0 };
  }
  if (answer.type === "score") {
    const labels = SCORE_LABELS[key] ?? [];
    const level = Math.round(answer.score ?? 0);
    return { text: labels[level] ?? (answer.score ?? 0).toFixed(1), p: answer.confidence ?? 0 };
  }
  const p = answer.noul ?? 0;
  if (p >= UNCERTAIN_LOW && p <= UNCERTAIN_HIGH) return { text: "Uncertain", p, uncertain: true };
  return { text: p > 0.5 ? "Yes" : "No", p: p > 0.5 ? p : 1 - p };
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
          const { text, p, uncertain } = describe(key, decisions[key]);
          const pct = Math.round(p * 100);
          if (compact) {
            return (
              <Badge key={key} tone={uncertain ? "warn" : "jev"} title={`${label}: ${pct}%`}>
                {label}: {text}
              </Badge>
            );
          }
          return (
            <div key={key} className="rounded-lg border border-jev/20 bg-jev-50 px-2.5 py-1.5" data-testid={`tag-${key}`}>
              <p className="text-[10px] font-medium uppercase tracking-wide text-jev/80">{label}</p>
              <p className={uncertain ? "text-sm font-medium text-warn-700" : "text-sm font-medium text-ink"}>{text}</p>
              <ProbBar value={p} tone={uncertain ? "warn" : "jev"} className="mt-1" />
              <p className="tabular mt-0.5 text-[10px] text-muted">
                {uncertain ? `${pct}% yes, too close to call` : `${pct}% probability`}
              </p>
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
