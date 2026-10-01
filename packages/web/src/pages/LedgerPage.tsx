import { Gavel } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AskButton } from "@/components/chat/AskButton";
import { EntryCard } from "@/components/ledger/EntryCard";
import { RuleComposer } from "@/components/rules/RuleComposer";
import { Button } from "@/components/ui/button";
import { useCube, useEntries, useReps } from "@/hooks/queries";
import { usePageContext } from "@/hooks/useChat";
import { useScope } from "@/hooks/useScope";
import { useSession } from "@/hooks/useSession";
import { monthName } from "@/lib/format";
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
  const [segmentId, setSegmentId] = useState<number | undefined>();
  const [userId, setUserId] = useState<string | undefined>();
  const [missedOnly, setMissedOnly] = useState(false);
  const { scope } = useScope();
  const { user } = useSession();
  const { data: cube } = useCube(scope);
  const { data: reps = [] } = useReps();
  const { data: entries, isLoading } = useEntries({ scope, segmentId, userId });
  const author = user?.role === "lead" || user?.role === "admin";
  const shown = missedOnly ? entries?.filter((e) => e.claim?.resolution === "contradicted") : entries;
  const [params] = useSearchParams();
  const linked = params.get("entry");
  usePageContext({ page: "ledger", segmentId: segmentId ?? null, entryId: linked });
  const ownsEntry = (e: Entry) => user?.role === "rep" && e.userId === user.id;
  const askAbout = (e: Entry) =>
    e.claim?.resolution === "contradicted"
      ? `Why was the claim on this ${monthName(e.month)} entry for micro-segment ${e.segmentId} contradicted?`
      : `Walk me through this ${monthName(e.month)} entry for micro-segment ${e.segmentId}.`;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">Demand ledger</h1>
          <p className="text-sm text-muted">
            Every number with its impact snapshot, flags, structured claim and how the claim turned out.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5 text-sm text-muted">
            <input type="checkbox" checked={missedOnly} onChange={(e) => setMissedOnly(e.target.checked)} aria-label="Missed claims only" />
            Missed claims only
          </label>
          <select
            aria-label="Segment filter"
            className="h-9 rounded-lg border border-line bg-surface px-2 text-sm"
            value={segmentId ?? ""}
            onChange={(e) => setSegmentId(e.target.value ? Number(e.target.value) : undefined)}
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
            onChange={(e) => setUserId(e.target.value || undefined)}
          >
            <option value="">All reps</option>
            {reps.map((r) => (
              <option key={r.user.id} value={r.user.id}>
                {r.user.name}
              </option>
            ))}
          </select>
        </div>
      </div>
      {isLoading && <p className="text-sm text-muted">Loading...</p>}
      <div className="flex flex-col gap-3" data-testid="ledger-list">
        {shown?.map((e) => (
          <EntryCard
            key={e.id}
            entry={e}
            highlight={e.id === linked}
            canNote={author || ownsEntry(e)}
            ask={
              e.source !== "history" && (author || ownsEntry(e)) ? (
                <AskButton
                  question={askAbout(e)}
                  context={{ page: "ledger", segmentId: e.segmentId, month: e.month, entryId: e.id }}
                />
              ) : undefined
            }
          >
            {author && scope && e.claim?.resolution === "contradicted" && <MissedClaimRule entry={e} scope={scope} />}
          </EntryCard>
        ))}
        {shown?.length === 0 && <p className="text-sm text-muted">No entries match these filters.</p>}
      </div>
    </div>
  );
}
