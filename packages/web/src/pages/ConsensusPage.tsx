import { CheckCheck, Download } from "lucide-react";
import { RtbPanel } from "@/components/consensus/RtbPanel";
import { EntryCard } from "@/components/ledger/EntryCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ProbBar } from "@/components/ui/prob-bar";
import { useToast } from "@/components/ui/toast";
import { useBulkApprove, useDecide } from "@/hooks/mutations";
import { useCube, useQueue } from "@/hooks/queries";
import { useScope } from "@/hooks/useScope";
import { useSession } from "@/hooks/useSession";
import { api, scopeQuery } from "@/lib/api";
import { fmtKs, monthName } from "@/lib/format";
import type { QueueItem } from "@/lib/types";

const TRIAGE_TONE = { approve: "brand", discuss: "warn", challenge: "crit" } as const;

function ExceptionCard({ item, canDecide }: { item: QueueItem; canDecide: boolean }) {
  const decide = useDecide();
  const toast = useToast();
  const triage = item.entry.triage;
  const act = (decision: string) =>
    decide.mutate(
      { entryId: item.entry.id, decision },
      { onError: (e) => toast({ tone: "error", title: "Decision failed", body: e.message }) },
    );
  return (
    <EntryCard entry={item.entry}>
      <div className="rounded-lg border border-warn-500/30 bg-warn-50 px-3 py-2 text-xs text-warn-700">
        <p className="font-medium">Why this is on the agenda</p>
        <ul className="ml-4 list-disc">
          {item.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        {triage && (
          <div className="flex min-w-60 items-center gap-2 text-xs" data-testid="triage">
            <span className="text-muted">Jev suggests</span>
            <Badge tone={TRIAGE_TONE[triage.choice]}>{triage.choice}</Badge>
            <ProbBar value={triage.confidence} className="w-20" />
            <span className="tabular text-muted">{Math.round(triage.confidence * 100)}%</span>
          </div>
        )}
        {canDecide && (
          <div className="flex gap-2">
            <Button size="sm" onClick={() => act("approve")} disabled={decide.isPending}>
              Approve
            </Button>
            <Button size="sm" variant="secondary" onClick={() => act("discuss")} disabled={decide.isPending}>
              Discuss
            </Button>
            <Button size="sm" variant="danger" onClick={() => act("challenge")} disabled={decide.isPending}>
              Challenge
            </Button>
          </div>
        )}
      </div>
    </EntryCard>
  );
}

export function ConsensusPage() {
  const { scope } = useScope();
  const { data: queue, isLoading } = useQueue(scope);
  const { data: cube } = useCube(scope);
  const { user } = useSession();
  const bulk = useBulkApprove();
  const toast = useToast();
  const isLead = user?.role === "lead" || user?.role === "admin";
  const exportCsv = () =>
    api
      .download(`/export/supply.csv?${scopeQuery(scope)}`, `supply-${scope?.countryCode}-${scope?.megaSegmentId}.csv`)
      .catch((e: Error) => toast({ tone: "error", title: "Export failed", body: e.message }));

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
      <section className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold">Consensus: exceptions only</h1>
            <p className="text-sm text-muted">
              The meeting only covers flagged numbers, wide ranges and reps with a weak track record. Everything else is
              approved in bulk.
            </p>
          </div>
          {!isLead && <Badge tone="warn">Only a consensus lead can decide</Badge>}
        </div>
        {isLoading && <p className="text-sm text-muted">Loading queue...</p>}
        <div className="flex flex-col gap-3" data-testid="exceptions">
          {queue?.exceptions.map((item) => <ExceptionCard key={item.entry.id} item={item} canDecide={isLead} />)}
          {queue && queue.exceptions.length === 0 && (
            <Card>
              <CardBody className="pt-4 text-sm text-muted">No exceptions. Nothing needs discussion this cycle.</CardBody>
            </Card>
          )}
        </div>
      </section>

      <aside className="flex flex-col gap-4">
        <Card>
          <CardHeader
            title={`Routine entries (${queue?.routine.length ?? 0})`}
            subtitle="No flags, reliable rep, specific justification"
            icon={<CheckCheck size={15} />}
          />
          <CardBody className="flex flex-col gap-2">
            {queue?.routine.map((e) => (
              <div key={e.id} className="flex items-center justify-between text-sm" data-testid="routine-entry">
                <span>
                  {e.segmentLabel} · {monthName(e.month)}
                </span>
                <span className="tabular text-muted">{fmtKs(e.value)}</span>
              </div>
            ))}
            <Button
              className="mt-1"
              disabled={!isLead || !queue?.routine.length || bulk.isPending}
              data-testid="bulk-approve"
              onClick={() =>
                bulk.mutate(scope, {
                  onSuccess: (r) => toast({ tone: "success", title: `Approved ${r.approved} routine entries` }),
                  onError: (e) => toast({ tone: "error", title: "Bulk approve failed", body: e.message }),
                })
              }
            >
              Bulk approve routine
            </Button>
          </CardBody>
        </Card>

        {cube && <RtbPanel countryCode={cube.countryCode} segments={cube.segments} />}

        <Card>
          <CardHeader
            title="Supply handoff"
            subtitle="Approved numbers as low / mid / high. Low-confidence lines are built to the low end."
            icon={<Download size={15} />}
          />
          <CardBody>
            <Button variant="secondary" className="w-full" onClick={exportCsv} data-testid="export-csv">
              Export supply range CSV
            </Button>
          </CardBody>
        </Card>
      </aside>
    </div>
  );
}
