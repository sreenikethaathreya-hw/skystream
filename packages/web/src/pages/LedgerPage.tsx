import { useState } from "react";
import { EntryCard } from "@/components/ledger/EntryCard";
import { useCube, useEntries } from "@/hooks/queries";
import { useDemoUser } from "@/hooks/useDemoUser";

export function LedgerPage() {
  const [segmentId, setSegmentId] = useState<number | undefined>();
  const [userId, setUserId] = useState<string | undefined>();
  const { data: cube } = useCube();
  const { users } = useDemoUser();
  const { data: entries, isLoading } = useEntries({ segmentId, userId });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">Demand ledger</h1>
          <p className="text-sm text-muted">
            Every number with its impact snapshot, flags, structured claim and how the claim turned out.
          </p>
        </div>
        <div className="flex gap-2">
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
            {users
              .filter((u) => u.role === "rep")
              .map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
          </select>
        </div>
      </div>
      {isLoading && <p className="text-sm text-muted">Loading...</p>}
      <div className="flex flex-col gap-3" data-testid="ledger-list">
        {entries?.map((e) => <EntryCard key={e.id} entry={e} />)}
        {entries?.length === 0 && <p className="text-sm text-muted">No entries match these filters.</p>}
      </div>
    </div>
  );
}
