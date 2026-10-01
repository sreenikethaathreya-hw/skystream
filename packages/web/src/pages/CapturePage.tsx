import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BaselinePanel } from "@/components/capture/BaselinePanel";
import { EntryPanel } from "@/components/capture/EntryPanel";
import { IbpPanel } from "@/components/capture/IbpPanel";
import { FlagsTile, HectaresTile, ShareTile, YtgTile } from "@/components/capture/ImpactTiles";
import { JustificationBox } from "@/components/capture/JustificationBox";
import { MonthGrid } from "@/components/capture/MonthGrid";
import { SegmentList } from "@/components/capture/SegmentList";
import { VolumePriceBar } from "@/components/capture/VolumePriceBar";
import { AskButton } from "@/components/chat/AskButton";
import { EntryNotes } from "@/components/ledger/EntryNotes";
import { TrackRecordInline } from "@/components/reps/TrackRecordInline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { useAnalyze, useJustifyEntry, useSubmitEntry } from "@/hooks/mutations";
import { useCube, useEntryNotes } from "@/hooks/queries";
import { useCaptureDraft } from "@/hooks/useCaptureDraft";
import { usePageContext } from "@/hooks/useChat";
import { useMoney } from "@/hooks/useMoney";
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

const LAST_YEAR_LABELS: Record<string, string> = {
  actuals: "monthly actuals",
  annual_actuals: "last year's annual actual sales (5-year sales file), phased by month",
};

export function CapturePage() {
  const { scope, loading: scopesLoading } = useScope();
  const { data: cube, isLoading, error } = useCube(scope);
  const { user } = useSession();
  const money = useMoney();
  const preferred =
    cube?.segments
      .filter((s) => s.editable)
      .sort((a, b) => b.context.planQtyKs - a.context.planQtyKs)[0]?.id ?? cube?.segments[0]?.id;
  const { segment, month, setMonth, draft, setDraft, entry, live, selectSegment } = useCaptureDraft(cube, preferred);
  const [justification, setJustification] = useState("");
  const [claim, setClaim] = useState<{ key: string; claim: StructuredClaim } | null>(null);
  const analyze = useAnalyze();
  const submit = useSubmitEntry();
  const justify = useJustifyEntry();
  const toast = useToast();
  const [params] = useSearchParams();
  const linkedSegment = Number(params.get("segment")) || undefined;
  const linkedMonth = Number(params.get("month")) || undefined;
  const cubeReady = !!cube;

  useEffect(() => {
    if (!cube) return;
    if (linkedSegment && cube.segments.some((s) => s.id === linkedSegment)) selectSegment(linkedSegment);
    if (linkedMonth && linkedMonth >= cube.clockMonth && linkedMonth <= 12) setMonth(linkedMonth);
    // Follow a deep link once the cube is there, and again whenever the link changes.
  }, [cubeReady, linkedSegment, linkedMonth]); // eslint-disable-line react-hooks/exhaustive-deps

  const current = segment?.latestEntries.find((e) => e.month === month && e.source !== "history");
  const notes = useEntryNotes(current?.id);
  usePageContext(segment ? { page: "capture", segmentId: segment.id, month, entryId: current?.id ?? null } : null);

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

  if (scopesLoading || isLoading) return <p className="text-sm text-muted">Loading your segments...</p>;
  if (!scope) return <p className="text-sm text-muted">No market data is loaded for your segments yet. Ask an admin to upload it.</p>;
  if (error || !cube) return <p className="text-sm text-crit-700">Could not load data: {String(error)}</p>;
  if (cube.yearClosed) {
    return <p className="text-sm text-muted">All twelve months of {cube.year} have actuals. Ask an admin to move the planning year forward.</p>;
  }
  if (!segment || !live || !payload) return <p className="text-sm text-muted">No active micro-segments in this scope.</p>;

  const owns = segment.editable;
  const needsJustification = live.flags.length > 0;
  const canSubmit = owns && entry.value >= 0 && (!needsJustification || justification.trim().length > 0) && !submit.isPending;

  const ibpMode = cube.demandSource === "ibp";
  const ibpMonth = ibpMode ? segment.ibp.find((m) => m.month === month) : undefined;
  const ibpEntry = ibpMonth?.entryId ? segment.latestEntries.find((e) => e.id === ibpMonth.entryId) : undefined;
  const whatIf = !!ibpMonth && Math.round(entry.value) !== Math.round(ibpMonth.qtyKs);
  const ownsIbp = !!ibpEntry && (ibpEntry.userId === user?.id || owns);
  const canJustify =
    ownsIbp && !whatIf && (!needsJustification || justification.trim().length > 0) && !justify.isPending;
  const resetToIbp = () => ibpMonth && setDraft({ ...draft, value: Math.round(ibpMonth.qtyKs) });
  const askContext = { page: "capture", segmentId: segment.id, month, entryId: current?.id ?? null };
  const typed = `${Math.round(entry.value)} KS (range ${Math.round(entry.low)} to ${Math.round(entry.high)})`;
  const where = `micro-segment ${segment.id} in ${monthName(month)}`;
  const savedMatches = !!current && Math.round(current.value) === Math.round(entry.value);

  const onJustify = () =>
    ibpEntry &&
    justify.mutate(
      { entryId: ibpEntry.id, justification: justification.trim() || null, low: entry.low, high: entry.high },
      {
        onSuccess: (saved) => {
          toast({
            tone: "success",
            title: `Justified ${fmtKs(saved.value)} for ${saved.segmentLabel}, ${monthName(saved.month)}`,
            body: saved.claim ? `Claim recorded; checked against ${monthName(saved.claim.checkMonth)} actuals.` : "Recorded in the ledger.",
          });
          setJustification("");
          setClaim(null);
        },
        onError: (e) => toast({ tone: "error", title: "Could not save the justification", body: e.message }),
      },
    );

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
        <SegmentList segments={cube.segments} selectedId={segment.id} onSelect={selectSegment} />
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
                <p className="mt-1 text-[11px] text-muted" data-testid="basis-note">
                  Monthly plan: {BASIS_LABELS[segment.planBasis] ?? segment.planBasis} · last year from{" "}
                  {LAST_YEAR_LABELS[segment.lastYearBasis] ?? "no data"}
                </p>
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
              money={money}
              committedInIbp={ibpMode ? (ibpMonth ? ibpMonth.qtyKs : null) : undefined}
            />
            {whatIf && (
              <p className="flex items-center gap-2 text-xs text-warn-700" data-testid="what-if-note">
                Showing a what-if. The committed number is {fmtKs(ibpMonth!.qtyKs)} in IBP; change it there.
                <Button size="sm" variant="ghost" onClick={resetToIbp}>Back to the IBP number</Button>
              </p>
            )}
          </CardBody>
        </Card>

        {ibpMode && (
          <IbpPanel
            month={month}
            ibp={ibpMonth}
            ask={
              ibpMonth && (
                <AskButton
                  question={`Which varieties make up my ${monthName(month)} IBP number for ${where}, and is anything flagged?`}
                  context={askContext}
                  testId="ask-ibp"
                />
              )
            }
          />
        )}

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
          <FlagsTile
            flags={live.flags}
            ask={(flag) => (
              <AskButton
                label="Why?"
                testId={`ask-flag-${flag.code}`}
                question={
                  savedMatches
                    ? `Why is my ${monthName(month)} entry for micro-segment ${segment.id} flagged for ${flag.code.replace(/_/g, " ")}?`
                    : `What if I enter ${typed} for ${where}: why does the ${flag.code.replace(/_/g, " ")} flag fire?`
                }
                context={askContext}
              />
            )}
          />
        </div>

        <VolumePriceBar revenue={live.impact.revenue} money={money} />

        <JustificationBox
          text={justification}
          required={needsJustification}
          claim={claim?.claim ?? null}
          stale={!!claim && claim.key !== payloadKey}
          analyzing={analyze.isPending}
          onChange={setJustification}
          onAnalyze={onAnalyze}
          ask={
            justification.trim() && (
              <AskButton
                label="Check with the assistant"
                testId="ask-justification"
                question={`For ${typed} on ${where}, is this justification specific enough: "${justification.trim()}"`}
                context={askContext}
              />
            )
          }
        />

        {current && (notes.data?.length || current.status === "discuss" || current.status === "challenged") ? (
          <EntryNotes entryId={current.id} notes={notes.data ?? []} canWrite={owns || ownsIbp} />
        ) : null}

        <div className="flex items-center justify-end gap-3">
          {needsJustification && !justification.trim() && !whatIf && (
            <span className="text-xs text-crit-700">Add a justification to submit a flagged number.</span>
          )}
          {ibpMode ? (
            <Button onClick={onJustify} disabled={!canJustify} data-testid="justify-entry">
              {justify.isPending
                ? "Saving..."
                : ibpEntry
                  ? `Submit ${monthName(month)} justification`
                  : `No IBP number for ${monthName(month)}`}
            </Button>
          ) : (
            <Button onClick={onSubmit} disabled={!canSubmit} data-testid="submit-entry">
              {submit.isPending ? "Submitting..." : `Submit ${monthName(month)} demand`}
            </Button>
          )}
        </div>
      </section>
    </div>
  );
}
