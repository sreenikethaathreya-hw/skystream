import { useMemo, useState } from "react";
import { EntryPanel } from "@/components/capture/EntryPanel";
import { FlagsTile, HectaresTile, ShareTile, YtgTile } from "@/components/capture/ImpactTiles";
import { JustificationBox } from "@/components/capture/JustificationBox";
import { MonthGrid } from "@/components/capture/MonthGrid";
import { SegmentList } from "@/components/capture/SegmentList";
import { VolumePriceBar } from "@/components/capture/VolumePriceBar";
import { TrackRecordInline } from "@/components/reps/TrackRecordInline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { useAnalyze, useSubmitEntry } from "@/hooks/mutations";
import { useCube } from "@/hooks/queries";
import { useCaptureDraft } from "@/hooks/useCaptureDraft";
import { useDemoUser } from "@/hooks/useDemoUser";
import { fmtKs, monthName } from "@/lib/format";
import type { EntryPayload, StructuredClaim } from "@/lib/types";

export function CapturePage() {
  const { data: cube, isLoading, error } = useCube();
  const { user, users } = useDemoUser();
  const preferred =
    cube?.segments
      .filter((s) => s.ownerId === user?.id)
      .sort((a, b) => b.context.planQtyKs - a.context.planQtyKs)[0]?.id ?? cube?.segments[0]?.id;
  const { segment, month, setMonth, draft, setDraft, entry, live, selectSegment } = useCaptureDraft(cube, preferred);
  const [justification, setJustification] = useState("");
  const [claim, setClaim] = useState<{ key: string; claim: StructuredClaim } | null>(null);
  const analyze = useAnalyze();
  const submit = useSubmitEntry();
  const toast = useToast();

  const payload: EntryPayload | undefined = useMemo(
    () =>
      segment && {
        segmentId: segment.id,
        month: entry.month,
        value: entry.value,
        low: entry.low,
        high: entry.high,
        price: entry.price,
        justification: justification.trim() || null,
      },
    [segment, entry, justification],
  );
  const payloadKey = JSON.stringify(payload);

  if (isLoading) return <p className="text-sm text-muted">Loading the locked scope...</p>;
  if (error || !cube || !segment || !live || !payload) return <p className="text-sm text-crit-700">Could not load data: {String(error)}</p>;

  const owns = user?.role === "rep" && segment.ownerId === user.id;
  const needsJustification = live.flags.length > 0;
  const canSubmit = owns && entry.value >= 0 && (!needsJustification || justification.trim().length > 0) && !submit.isPending;

  const onAnalyze = () =>
    analyze.mutate(payload, {
      onSuccess: (r) => r.claim && setClaim({ key: payloadKey, claim: r.claim }),
      onError: (e) => toast({ tone: "error", title: "Could not structure", body: e.message }),
    });

  const onSubmit = () =>
    submit.mutate(payload, {
      onSuccess: (saved) => {
        toast({
          tone: "success",
          title: `Submitted ${fmtKs(saved.value)} for ${saved.segmentLabel}, ${monthName(saved.month)}`,
          body: saved.claim ? `Claim recorded; checked against ${monthName(saved.claim.checkMonth)} actuals.` : "Recorded in the ledger.",
        });
        setJustification("");
        setClaim(null);
      },
      onError: (e) => toast({ tone: "error", title: "Submit failed", body: e.message }),
    });

  return (
    <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
      <aside className="flex flex-col gap-4">
        <SegmentList segments={cube.segments} selectedId={segment.id} user={user} users={users} onSelect={selectSegment} />
        {user?.role === "rep" && <TrackRecordInline userId={user.id} />}
      </aside>

      <section className="flex min-w-0 flex-col gap-4">
        <Card>
          <CardBody className="flex flex-col gap-4 pt-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h1 className="text-lg font-semibold" data-testid="segment-title">
                  {segment.label}
                </h1>
                <p className="text-xs text-muted">{segment.description}</p>
                {segment.planComment && <p className="mt-1 max-w-3xl text-xs italic text-muted">"{segment.planComment}"</p>}
              </div>
              {!owns && (
                <Badge tone="warn">
                  {user?.role === "lead" ? "Switch to the owning rep to submit" : "View only: owned by another rep"}
                </Badge>
              )}
            </div>
            <MonthGrid segment={segment} selectedMonth={month} draftValue={entry.value} onSelect={setMonth} />
            <EntryPanel
              month={month}
              planMonth={segment.context.monthlyPlan[month - 1]}
              planNetPrice={segment.context.planNetPrice}
              draft={draft}
              onChange={setDraft}
            />
          </CardBody>
        </Card>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <ShareTile impact={live.impact} />
          <YtgTile impact={live.impact} />
          <HectaresTile impact={live.impact} />
          <FlagsTile flags={live.flags} />
        </div>

        <VolumePriceBar revenue={live.impact.revenue} />

        <JustificationBox
          text={justification}
          required={needsJustification}
          claim={claim?.claim ?? null}
          stale={!!claim && claim.key !== payloadKey}
          analyzing={analyze.isPending}
          onChange={setJustification}
          onAnalyze={onAnalyze}
        />

        <div className="flex items-center justify-end gap-3">
          {needsJustification && !justification.trim() && (
            <span className="text-xs text-crit-700">Add a justification to submit a flagged number.</span>
          )}
          <Button onClick={onSubmit} disabled={!canSubmit} data-testid="submit-entry">
            {submit.isPending ? "Submitting..." : `Submit ${monthName(month)} demand`}
          </Button>
        </div>
      </section>
    </div>
  );
}
