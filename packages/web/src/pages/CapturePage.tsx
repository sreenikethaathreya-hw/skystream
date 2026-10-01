import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { BaselinePanel } from "@/components/capture/BaselinePanel";
import { DemandInstrument, LeadCheck } from "@/components/capture/DemandInstrument";
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
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useAnalyze, useSubmitEntry } from "@/hooks/mutations";
import { useCube } from "@/hooks/queries";
import { useCaptureDraft } from "@/hooks/useCaptureDraft";
import { useScope } from "@/hooks/useScope";
import { useSession } from "@/hooks/useSession";
import { fmtKs, monthName } from "@/lib/format";
import type { EntryPayload, StructuredClaim } from "@/lib/types";

const BASIS_LABELS: Record<string, string> = {
  synthetic: "synthetic seasonal curve (demo)",
  seasonality_micro: "uploaded seasonality (micro-segment)",
  seasonality_mega: "uploaded seasonality (mega-segment)",
  actuals_profile: "shape of the last two years of actuals",
  flat: "flat split (no seasonality or actuals history yet)",
  none: "no plan",
};

function CaptureSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-[260px_1fr]" role="status">
      <span className="sr-only">Loading your segments…</span>
      <div className="flex flex-col gap-2">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-14" />
        ))}
      </div>
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-5 rounded-lg border border-line bg-surface p-5">
          <Skeleton className="h-6 w-56" />
          <Skeleton className="h-16" />
          <Skeleton className="h-16 w-72" />
          <Skeleton className="h-14" />
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-40 rounded-lg" />
          ))}
        </div>
      </div>
    </div>
  );
}

function useUnsavedGuard(active: boolean) {
  useEffect(() => {
    if (!active) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [active]);
}

export function CapturePage() {
  const { scope, loading: scopesLoading } = useScope();
  const { data: cube, isLoading, error } = useCube(scope);
  const { user } = useSession();
  const preferred = useMemo(() => {
    let best: { id: number; plan: number } | undefined;
    for (const s of cube?.segments ?? []) {
      if (s.editable && (!best || s.context.planQtyKs > best.plan)) best = { id: s.id, plan: s.context.planQtyKs };
    }
    return best?.id ?? cube?.segments[0]?.id;
  }, [cube]);
  const { segment, month, setMonth, draft, setDraft, dirty, markSaved, entry, live, selectSegment } = useCaptureDraft(
    cube,
    preferred,
  );
  const [justification, setJustification] = useState("");
  const [claim, setClaim] = useState<{ key: string; claim: StructuredClaim } | null>(null);
  const analyze = useAnalyze();
  const submit = useSubmitEntry();
  const toast = useToast();
  useUnsavedGuard(dirty || justification.trim().length > 0);

  const payload: EntryPayload | undefined = useMemo(
    () =>
      segment &&
      cube && {
        countryCode: cube.countryCode,
        segmentId: segment.id,
        month: entry.month,
        value: entry.value,
        low: entry.low,
        high: entry.high,
        price: entry.price,
        justification: justification.trim() || null,
      },
    [segment, cube, entry, justification],
  );
  const payloadKey = JSON.stringify(payload);

  const isAdmin = user?.role === "admin";
  const uploadAction = isAdmin ? (
    <Link to="/admin/data" className="text-sm font-medium text-brand-700 underline underline-offset-4">
      Open Admin data
    </Link>
  ) : undefined;

  if (scopesLoading || isLoading) return <CaptureSkeleton />;
  if (!scope) {
    return (
      <EmptyState title="No market data for your segments yet" action={uploadAction}>
        {isAdmin ? "Upload the market and plan files under Admin data." : "Your admin uploads it under Admin data. Check back once they have."}
      </EmptyState>
    );
  }
  if (error || !cube) {
    return (
      <EmptyState
        title="Could not load your segments"
        action={
          <Button variant="secondary" onClick={() => window.location.reload()}>
            Reload
          </Button>
        }
      >
        If it keeps failing, ask an admin.
      </EmptyState>
    );
  }
  if (cube.yearClosed) {
    return (
      <EmptyState title={`${cube.year} is closed`} action={uploadAction}>
        All twelve months have actuals. {isAdmin ? "Move the planning year forward under Admin data." : "Ask an admin to move the planning year forward."}
      </EmptyState>
    );
  }
  if (!segment || !live || !payload) {
    return (
      <EmptyState title="No active micro-segments here" action={uploadAction}>
        Switch the country or mega-segment above, or ask an admin to assign you segments.
      </EmptyState>
    );
  }

  const owns = segment.editable;
  const needsJustification = live.flags.length > 0;
  const leadFlag = live.flags.find((f) => f.severity === "critical") ?? live.flags[0];
  const missingReason = needsJustification && !justification.trim();
  const canSubmit = owns && entry.value >= 0 && !missingReason && !submit.isPending;

  const onAnalyze = () =>
    analyze.mutate(payload, {
      onSuccess: (r) => r.claim && setClaim({ key: payloadKey, claim: r.claim }),
      onError: (e) => toast({ tone: "error", title: "Could not check the reason", body: `${e.message} Try again in a moment.` }),
    });

  const onSubmit = () =>
    submit.mutate(payload, {
      onSuccess: (saved) => {
        toast({
          tone: "success",
          title: `Submitted ${fmtKs(saved.value)} for ${saved.segmentLabel}, ${monthName(saved.month)}`,
          body: saved.claim ? `Reason recorded; checked against ${monthName(saved.claim.checkMonth)} actuals.` : "Recorded in the ledger.",
        });
        setJustification("");
        setClaim(null);
        markSaved();
      },
      onError: (e) => toast({ tone: "error", title: "Submit failed", body: `${e.message} Your number is still here; try again.` }),
    });

  return (
    <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
      <aside className="flex flex-col gap-4">
        <SegmentList segments={cube.segments} selectedId={segment.id} onSelect={selectSegment} />
        {user?.role === "rep" && <TrackRecordInline userId={user.id} />}
      </aside>

      <section className="flex min-w-0 flex-col gap-4">
        <Card className="border-ink/15 shadow-[0_1px_2px_rgb(22_33_26/0.05),0_12px_32px_-16px_rgb(22_33_26/0.25)]">
          <CardBody className="flex flex-col gap-5 pt-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h1 className="text-lg font-semibold" data-testid="segment-title">
                  {segment.label}
                </h1>
                <p className="break-words text-xs text-muted">{segment.description}</p>
                {segment.planComment && (
                  <p className="mt-1 max-w-3xl text-xs italic text-muted">“{segment.planComment}”</p>
                )}
                {user?.role !== "rep" && (
                  <p className="mt-1 text-[11px] text-muted" data-testid="basis-note">
                    Monthly plan: {BASIS_LABELS[segment.planBasis] ?? segment.planBasis} · last year from{" "}
                    {segment.lastYearBasis === "actuals"
                      ? "monthly actuals"
                      : segment.lastYearBasis === "plan"
                        ? "last year's plan (actuals incomplete)"
                        : "no data"}
                  </p>
                )}
              </div>
              {!owns && (
                <Badge tone="warn">
                  {user?.role === "rep"
                    ? `View only: ${segment.ownerNames.join(", ") || "no rep assigned"}`
                    : "View only: only assigned reps submit"}
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
            <DemandInstrument impact={live.impact} entry={entry} flags={live.flags} />
            <LeadCheck flag={leadFlag} more={live.flags.length - 1} />
          </CardBody>
        </Card>

        <BaselinePanel
          ctx={segment.context}
          impact={live.impact}
          month={month}
          value={entry.value}
          megaName={cube.megaSegmentDesc}
        />

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <ShareTile impact={live.impact} megaName={cube.megaSegmentDesc} />
          <YtgTile impact={live.impact} />
          <HectaresTile impact={live.impact} />
          <FlagsTile flags={live.flags} shownAbove={leadFlag?.code} />
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
          <p role="status" className="text-xs text-crit-700">
            {missingReason ? "Add a reason to submit a flagged number." : ""}
          </p>
          <Button onClick={onSubmit} disabled={!canSubmit} data-testid="submit-entry">
            {submit.isPending ? "Submitting…" : `Submit ${monthName(month)} demand`}
          </Button>
        </div>
      </section>
    </div>
  );
}
