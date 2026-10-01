import { RuleComposer } from "@/components/rules/RuleComposer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { useRetireRule } from "@/hooks/mutations";
import { useRules } from "@/hooks/queries";
import { useScope } from "@/hooks/useScope";
import { useSession } from "@/hooks/useSession";
import type { LeadRule } from "@/lib/types";

function RuleCard({ rule, canRetire }: { rule: LeadRule; canRetire: boolean }) {
  const retire = useRetireRule();
  const toast = useToast();
  const s = rule.stats;
  return (
    <Card data-testid="rule-card" className={rule.active ? "" : "opacity-70"}>
      <CardBody className="flex flex-col gap-2 pt-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={rule.active ? "brand" : "neutral"}>{rule.active ? "active" : "retired"}</Badge>
            <Badge tone={rule.slots.severity === "critical" ? "crit" : "warn"}>{rule.slots.severity}</Badge>
            <span className="text-xs text-muted">
              #{rule.id} by {rule.createdByName} · {new Date(rule.createdAt).toLocaleDateString()}
              {rule.retiredAt && ` · retired by ${rule.retiredByName} ${new Date(rule.retiredAt).toLocaleDateString()}`}
            </span>
          </div>
          {rule.active && canRetire && (
            <Button
              variant="secondary"
              size="sm"
              disabled={retire.isPending}
              onClick={() =>
                retire.mutate(rule.id, {
                  onSuccess: () => toast({ tone: "success", title: `Rule #${rule.id} retired` }),
                  onError: (e) => toast({ tone: "error", title: "Could not retire", body: e.message }),
                })
              }
            >
              Retire
            </Button>
          )}
        </div>
        <p className="text-sm font-medium">{rule.description}</p>
        <p className="text-xs italic text-muted">"{rule.text}"</p>
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

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold">Lead rules</h1>
        <p className="max-w-3xl text-sm text-muted">
          Lessons from missed numbers, written in plain language by the consensus lead and checked on every entry from then on,
          alongside the built-in plausibility flags. Each rule is a fixed, explainable check; the AI only reads the sentence once.
        </p>
      </div>

      {author && scope && (
        <Card>
          <CardHeader title="New rule" subtitle="Describe what should be flagged. Include the limit as a number." />
          <CardBody>
            <RuleComposer scope={scope} />
          </CardBody>
        </Card>
      )}

      {isLoading && <p className="text-sm text-muted">Loading...</p>}
      <div className="flex flex-col gap-3" data-testid="rule-list">
        {rules?.map((r) => <RuleCard key={r.id} rule={r} canRetire={author} />)}
        {rules?.length === 0 && <p className="text-sm text-muted">No lead rules for this scope yet.</p>}
      </div>
    </div>
  );
}
