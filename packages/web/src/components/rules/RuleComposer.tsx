import { Gavel, Sparkles } from "lucide-react";
import { useState } from "react";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { useCompileRule, useCreateRule } from "@/hooks/mutations";
import { fmtNum } from "@/lib/format";
import { METRICS } from "@/lib/leadRules";
import type { RuleDraft, Scope } from "@/lib/types";

export const DRIVER_LABELS: Record<string, string> = {
  pest_disease: "pest or disease pressure",
  competitor_move: "a competitor move",
  launch_phaseout: "a launch or phase-out",
  price: "price",
  area_change: "a change in planted area",
  weather_water: "weather or water",
  customer_win_loss: "a customer win or loss",
};

const SLOT_NAMES: Record<string, string> = {
  metric: "measure",
  comparator: "direction",
  applies_to: "scope",
  required_driver: "required reason",
  severity: "severity",
};

const EXAMPLES = [
  "Do not accept autumn increases above 20% over last year for any segment unless the rep names a competitor move.",
  "Flag any month more than 30% above its historical average.",
  "For this segment, challenge share jumps of more than 8 pts from one entry.",
];

function Preview({ draft }: { draft: RuleDraft }) {
  const p = draft.preview;
  if (!p || !draft.slots) return null;
  const unit = METRICS[draft.slots.metric]?.[1] ?? "";
  return (
    <div className="rounded-lg border border-line bg-canvas px-3 py-2 text-xs" data-testid="rule-preview">
      <p className="font-medium">
        Backtest: would have fired on {p.fired} of {p.checked} recorded entries
        {p.fired > 0 && ` (${p.contradicted} later contradicted, ${p.confirmed} confirmed, ${p.pending + p.inconclusive} open)`}.
      </p>
      {p.catchesSource !== null && (
        <p className={p.catchesSource ? "text-brand-700" : "text-crit-700"}>
          {p.catchesSource ? "It would have caught the missed entry." : "It would not have caught the missed entry; tighten the limit."}
        </p>
      )}
      {p.examples.length > 0 && (
        <ul className="mt-1 flex flex-col gap-0.5 text-muted">
          {p.examples.map((e) => (
            <li key={e.entryId} className="tabular flex flex-wrap items-center gap-2">
              <span>
                {e.label} · {e.userName} · {fmtNum(e.value)} KS ({e.metricValue >= 0 ? "+" : ""}
                {e.metricValue.toFixed(1)}
                {unit})
              </span>
              {e.resolution && <StatusBadge status={e.resolution} />}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function RuleComposer({
  scope,
  sourceEntryId,
  initialText = "",
  onDone,
}: {
  scope: Scope;
  sourceEntryId?: string;
  initialText?: string;
  onDone?: () => void;
}) {
  const [text, setText] = useState(initialText);
  const [draft, setDraft] = useState<{ text: string; draft: RuleDraft } | null>(null);
  const compile = useCompileRule();
  const create = useCreateRule();
  const toast = useToast();
  const request = { ...scope, text: text.trim(), sourceEntryId: sourceEntryId ?? null };
  const current = draft && draft.text === text.trim() ? draft.draft : null;

  const onCheck = () =>
    compile.mutate(request, {
      onSuccess: (d) => setDraft({ text: request.text, draft: d }),
      onError: (e) => toast({ tone: "error", title: "Could not read the rule", body: e.message }),
    });

  const onActivate = () => {
    if (!current?.slots) return;
    create.mutate(
      { ...request, slots: current.slots, provider: current.provider, decisions: current.decisions },
      {
        onSuccess: () => {
          toast({ tone: "success", title: "Rule is live", body: "Reps see it on their next keystroke in Capture." });
          setText("");
          setDraft(null);
          onDone?.();
        },
        onError: (e) => toast({ tone: "error", title: "Could not save the rule", body: e.message }),
      },
    );
  };

  return (
    <div className="flex flex-col gap-3" data-testid="rule-composer">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={2}
        maxLength={600}
        aria-label="Rule in plain language"
        placeholder={EXAMPLES[0]}
        className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm"
      />
      {!text && (
        <div className="flex flex-wrap gap-1.5">
          {EXAMPLES.map((ex) => (
            <button key={ex} type="button" onClick={() => setText(ex)} className="rounded-full border border-line px-2 py-0.5 text-[11px] text-muted hover:bg-canvas">
              {ex}
            </button>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2">
        <Button variant="jev" size="sm" onClick={onCheck} disabled={text.trim().length < 5 || compile.isPending} data-testid="check-rule">
          <Sparkles size={13} /> {compile.isPending ? "Reading…" : "Check rule"}
        </Button>
        <span className="text-[11px] text-muted">The AI only picks from fixed options; the limit and months come from your words.</span>
      </div>

      {current && !current.ok && (
        <p className="rounded-lg border border-crit-500/30 bg-crit-50 px-3 py-2 text-xs text-crit-700" data-testid="rule-rejection">
          {current.rejection}
        </p>
      )}

      {current?.ok && current.slots && (
        <div className="flex flex-col gap-2 rounded-lg border border-jev/30 bg-jev-50/40 px-3 py-2">
          <p className="text-sm font-medium" data-testid="rule-description">
            {current.description}
          </p>
          <div className="flex flex-wrap gap-1.5 text-[11px]">
            <Badge tone="jev">{METRICS[current.slots.metric]?.[0] ?? current.slots.metric}</Badge>
            <Badge tone="jev">
              {current.slots.comparator} {current.slots.threshold > 0 && METRICS[current.slots.metric]?.[2] ? "+" : ""}
              {current.slots.threshold}
              {METRICS[current.slots.metric]?.[1]}
            </Badge>
            <Badge>{current.slots.segmentIds ? `segments ${current.slots.segmentIds.join(", ")}` : "whole mega-segment"}</Badge>
            <Badge>{current.slots.months ? `months ${current.slots.months.join(", ")}` : "all months"}</Badge>
            {current.slots.requiredDriver && <Badge tone="info">must cite {DRIVER_LABELS[current.slots.requiredDriver]}</Badge>}
            <Badge tone={current.slots.severity === "critical" ? "crit" : "warn"}>{current.slots.severity}</Badge>
          </div>
          <p className="text-[11px] text-muted">
            Read by {current.provider}
            {current.lowConfidenceFields.length > 0 &&
              `; unsure about ${current.lowConfidenceFields.map((f) => SLOT_NAMES[f] ?? f).join(", ")}, so check the read-back`}
            .
          </p>
          <Preview draft={current} />
          <div className="flex justify-end">
            <Button size="sm" onClick={onActivate} disabled={create.isPending} data-testid="activate-rule">
              <Gavel size={13} /> {create.isPending ? "Saving…" : "Activate rule"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
