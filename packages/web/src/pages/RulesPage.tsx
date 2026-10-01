import { useEffect, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { AskButton } from "@/components/chat/AskButton";
import { RuleComposer } from "@/components/rules/RuleComposer";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ConfirmButton } from "@/components/ui/confirm-button";
import { PageHeader } from "@/components/ui/page-header";
import { useToast } from "@/components/ui/toast";
import { useRetireRule } from "@/hooks/mutations";
import { useRules } from "@/hooks/queries";
import { usePageContext } from "@/hooks/useChat";
import { useScope } from "@/hooks/useScope";
import { useSession } from "@/hooks/useSession";
import { fmtDate } from "@/lib/format";
import type { LeadRule } from "@/lib/types";
import { cn } from "@/lib/utils";

function RuleCard({ rule, canRetire, highlight }: { rule: LeadRule; canRetire: boolean; highlight: boolean }) {
  const retire = useRetireRule();
  const toast = useToast();
  const s = rule.stats;
  const card = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (highlight) card.current?.scrollIntoView?.({ block: "center", behavior: "smooth" });
  }, [highlight]);
  return (
    <Card
      ref={card}
      data-testid="rule-card"
      className={cn(!rule.active && "opacity-70", highlight && "ring-2 ring-brand-500/60")}
    >
      <CardBody className="flex flex-col gap-2 pt-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={rule.active ? "brand" : "neutral"}>{rule.active ? "active" : "retired"}</Badge>
            <Badge tone={rule.slots.severity === "critical" ? "crit" : "warn"}>{rule.slots.severity}</Badge>
            <span className="text-xs text-muted">
              #{rule.id} by {rule.createdByName} · {fmtDate(rule.createdAt)}
              {rule.retiredAt && ` · retired by ${rule.retiredByName} ${fmtDate(rule.retiredAt)}`}
            </span>
            <AskButton
              question={`How has lead rule ${rule.id} performed: how often did it fire and were those entries right?`}
              context={{ page: "rules", ruleId: rule.id }}
            />
          </div>
          {rule.active && canRetire && (
            <ConfirmButton
              variant="secondary"
              size="sm"
              disabled={retire.isPending}
              confirmLabel="Confirm retire"
              onConfirm={() =>
                retire.mutate(rule.id, {
                  onSuccess: () => toast({ tone: "success", title: `Rule #${rule.id} retired` }),
                  onError: (e) => toast({ tone: "error", title: "Could not retire", body: e.message }),
                })
              }
            >
              Retire
            </ConfirmButton>
          )}
        </div>
        <p className="text-sm font-medium">{rule.description}</p>
        <p className="break-words text-xs italic text-muted">“{rule.text}”</p>
        {rule.sourceLabel && <p className="text-xs text-muted">Written after the miss on {rule.sourceLabel}.</p>}
        <p className="tabular text-xs text-muted">
          Fired on {s.fired} {s.fired === 1 ? "entry" : "entries"} since it went live
          {s.fired > 0 && `: ${s.contradicted} later contradicted, ${s.confirmed} confirmed, ${s.pending + s.inconclusive} open`}
          . Read by {rule.provider}.
        </p>
      </CardBody>
    </Card>
  );
}

export function RulesPage() {
  const { scope } = useScope();
  const { user } = useSession();
  const { data: rules, isLoading } = useRules(scope);
  const author = user?.role === "lead" || user?.role === "admin";
  const [params] = useSearchParams();
  const linked = Number(params.get("rule")) || null;
  usePageContext({ page: "rules", ruleId: linked });

  return (
    <div className="flex flex-col gap-4">
      <PageHeader eyebrow="Guardrails" title="Lead rules">
        Lessons from missed numbers, written in plain language by the consensus lead and checked on every entry from then on,
        alongside the built-in plausibility flags. Each rule is a fixed, explainable check; the AI only reads the sentence once.
      </PageHeader>

      {author && scope && (
        <Card>
          <CardHeader title="New rule" subtitle="Describe what should be flagged. Include the limit as a number." />
          <CardBody>
            <RuleComposer scope={scope} />
          </CardBody>
        </Card>
      )}

      {isLoading && <p className="text-sm text-muted">Loading…</p>}
      <div className="flex flex-col gap-3" data-testid="rule-list">
        {rules?.map((r) => <RuleCard key={r.id} rule={r} canRetire={author} highlight={r.id === linked} />)}
        {rules?.length === 0 && <p className="text-sm text-muted">No lead rules for this scope yet.</p>}
      </div>
    </div>
  );
}
