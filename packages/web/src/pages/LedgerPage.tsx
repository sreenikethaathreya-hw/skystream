import { Gavel } from "lucide-react";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { LedgerHeader, LedgerRow, groupByMonth } from "@/components/ledger/LedgerRows";
import { RuleComposer } from "@/components/rules/RuleComposer";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { useCube, useEntries, useReps } from "@/hooks/queries";
import { useScope } from "@/hooks/useScope";
import { useSession } from "@/hooks/useSession";
import type { Entry, Scope } from "@/lib/types";

function MissedClaimRule({ entry, scope }: { entry: Entry; scope: Scope }) {
  const [open, setOpen] = useState(false);
  if (!open) {
    return (
      <div className="flex justify-end">
        <Button variant="secondary" size="sm" onClick={() => setOpen(true)} data-testid="add-rule-from-miss">
          <Gavel size={13} /> Turn this miss into a rule
        </Button>
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-line p-3">
      <p className="mb-2 text-xs text-muted">
        What should be checked on future entries so this does not slip through again? The rule starts from this entry's
        micro-segment unless you say it covers every segment.
      </p>
      <RuleComposer scope={scope} sourceEntryId={entry.id} onDone={() => setOpen(false)} />
    </div>
  );
}

export function LedgerPage() {
  const [params, setParams] = useSearchParams();
  const segmentId = Number(params.get("segment")) || undefined;
  const userId = params.get("rep") ?? undefined;
  const missedOnly = params.get("missed") === "1";
  const setFilter = (name: string, value: string | undefined) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value) next.set(name, value);
        else next.delete(name);
        return next;
      },
      { replace: true },
    );
  const { scope } = useScope();
  const { user } = useSession();
  const { data: cube } = useCube(scope);
  const { data: reps = [] } = useReps();
  const { data: entries, isLoading } = useEntries({ scope, segmentId, userId });
  const author = user?.role === "lead" || user?.role === "admin";
  const shown = missedOnly ? entries?.filter((e) => e.claim?.resolution === "contradicted") : entries;
  const groups = useMemo(() => groupByMonth(shown ?? []), [shown]);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="Audit trail"
        title="Demand ledger"
        actions={
          <>
            <label className="flex items-center gap-1.5 text-sm text-muted">
              <input type="checkbox" defaultChecked={missedOnly} onChange={(e) => setFilter("missed", e.target.checked ? "1" : undefined)} />
              Missed claims only
            </label>
            <select
              aria-label="Segment filter"
              className="h-9 rounded-lg border border-line bg-surface px-2 text-sm"
              value={segmentId ?? ""}
              onChange={(e) => setFilter("segment", e.target.value || undefined)}
            >
              <option value="">All segments</option>
              {cube?.segments.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
            <select
              aria-label="Rep filter"
              className="h-9 rounded-lg border border-line bg-surface px-2 text-sm"
              value={userId ?? ""}
              onChange={(e) => setFilter("rep", e.target.value || undefined)}
            >
              <option value="">All reps</option>
              {reps.map((r) => (
                <option key={r.user.id} value={r.user.id}>
                  {r.user.name}
                </option>
              ))}
            </select>
          </>
        }
      >
        Every number with the reason given, and what actually happened.
      </PageHeader>
      {isLoading && (
        <div className="flex flex-col gap-2" role="status">
          <span className="sr-only">Loading the ledger…</span>
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
      )}
      <div className="flex flex-col gap-6" data-testid="ledger-list">
        {groups.map((g) => (
          <section key={g.key} aria-labelledby={`ledger-${g.key}`}>
            <h2 id={`ledger-${g.key}`} className="mb-2 flex items-baseline gap-2">
              <span className="font-num text-lg font-semibold">{g.label}</span>
              <span className="tabular text-xs text-muted">
                {g.entries.length} {g.entries.length === 1 ? "entry" : "entries"}
              </span>
            </h2>
            <LedgerHeader />
            <ol className="rounded-lg border border-line bg-surface">
              {g.entries.map((e) => (
                <LedgerRow key={e.id} entry={e}>
                  {author && scope && e.claim?.resolution === "contradicted" && <MissedClaimRule entry={e} scope={scope} />}
                </LedgerRow>
              ))}
            </ol>
          </section>
        ))}
        {shown?.length === 0 && (
          <p className="text-sm text-muted">No entries match these filters. Clear a filter above to see more.</p>
        )}
      </div>
    </div>
  );
}
