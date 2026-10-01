import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { BaselinePanel } from "@/components/capture/BaselinePanel";
import { Checks, DemandInstrument } from "@/components/capture/DemandInstrument";
import { EntryPanel } from "@/components/capture/EntryPanel";
import { HectaresTile, ShareTile, YtgTile } from "@/components/capture/ImpactTiles";
import { IbpPanel } from "@/components/capture/IbpPanel";
import { JustificationBox } from "@/components/capture/JustificationBox";
import { MonthGrid } from "@/components/capture/MonthGrid";
import { SegmentList } from "@/components/capture/SegmentList";
import { SubmitBar, type SubmitAction } from "@/components/capture/SubmitBar";
import { SubmitReceipt } from "@/components/capture/SubmitReceipt";
import { VolumePriceBar } from "@/components/capture/VolumePriceBar";
import { AskButton } from "@/components/chat/AskButton";
import { EntryNotes } from "@/components/ledger/EntryNotes";
import { TrackRecordInline } from "@/components/reps/TrackRecordInline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useAnalyze, useJustifyEntry, useSubmitEntry } from "@/hooks/mutations";
import { useCube, useEntryNotes } from "@/hooks/queries";
import { useCaptureDraft } from "@/hooks/useCaptureDraft";
import { usePageContext } from "@/hooks/useChat";
import { useMoney } from "@/hooks/useMoney";
import { useScope } from "@/hooks/useScope";
import { useSession } from "@/hooks/useSession";
import { fmtKs, monthName } from "@/lib/format";
import type { Entry, EntryPayload, StructuredClaim } from "@/lib/types";

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
  plan: "last year's plan (actuals incomplete)",
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
        <div className="flex flex-col gap-4 rounded-lg border border-line bg-surface p-5">
          <Skeleton className="h-6 w-56" />
          <Skeleton className="h-24" />
        </div>
        <Skeleton className="h-44 rounded-lg" />
        <div className="flex flex-col gap-5 rounded-lg border border-line bg-surface p-5">
          <Skeleton className="h-16 w-72" />
          <Skeleton className="h-14" />
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
  const money = useMoney();
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
  const [saved, setSaved] = useState<{ key: string; entry: Entry } | null>(null);
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
  const cellKey = `${segment.id}|${month}`;
  const receipt = saved && saved.key === cellKey && !dirty ? saved.entry : null;
  const missingReason = needsJustification && !justification.trim();
  const canSubmit = owns && entry.value >= 0 && !missingReason && !submit.isPending;

  const ibpMode = cube.demandSource === "ibp";
  const ibpMonth = ibpMode ? segment.ibp.find((m) => m.month === month) : undefined;
  const ibpEntry = ibpMonth?.entryId ? segment.latestEntries.find((e) => e.id === ibpMonth.entryId) : undefined;
  const whatIf = !!ibpMonth && Math.round(entry.value) !== Math.round(ibpMonth.qtyKs);
  const ownsIbp = !!ibpEntry && (ibpEntry.userId === user?.id || owns);
  const canJustify = ownsIbp && !whatIf && (!needsJustification || justification.trim().length > 0) && !justify.isPending;
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
        onSuccess: (savedEntry) => {
          toast({
            tone: "success",
            title: `Justified ${fmtKs(savedEntry.value)} for ${savedEntry.segmentLabel}, ${monthName(savedEntry.month)}`,
            body: savedEntry.claim
              ? `Claim recorded; checked against ${monthName(savedEntry.claim.checkMonth)} actuals.`
              : "Recorded in the ledger.",
          });
          setJustification("");
          setClaim(null);
          markSaved();
        },
        onError: (e) => toast({ tone: "error", title: "Could not save the justification", body: e.message }),
      },
    );

  const onAnalyze = () =>
    analyze.mutate(payload, {
      onSuccess: (r) => r.claim && setClaim({ key: payloadKey, claim: r.claim }),
      onError: (e) => toast({ tone: "error", title: "Could not check the reason", body: `${e.message} Try again in a moment.` }),
    });

  const onSubmit = () =>
    submit.mutate(payload, {
      onSuccess: (savedEntry) => {
        setSaved({ key: cellKey, entry: savedEntry });
        setJustification("");
        setClaim(null);
        markSaved();
      },
      onError: (e) => toast({ tone: "error", title: "Submit failed", body: `${e.message} Your number is still here; try again.` }),
    });

  const action: SubmitAction = ibpMode
    ? {
        label: justify.isPending
          ? "Saving…"
          : ibpEntry
            ? `Submit ${monthName(month)} justification`
            : `No IBP number for ${monthName(month)}`,
        onClick: () => void onJustify(),
        disabled: !canJustify,
        testId: "justify-entry",
      }
    : {
        label: submit.isPending ? "Submitting…" : `Submit ${monthName(month)} demand`,
        onClick: onSubmit,
        disabled: !canSubmit,
        testId: "submit-entry",
      };
  const reasonMissing = ibpMode ? needsJustification && !justification.trim() : missingReason;
  const blocker = whatIf ? "What-if only: go back to the IBP number to submit" : reasonMissing ? "Add a reason to submit a flagged number" : null;
  const onFixBlocker = reasonMissing && !whatIf ? () => document.getElementById("justification")?.focus() : undefined;

  return (
    <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
      <aside className="flex flex-col gap-4">
        <SegmentList segments={cube.segments} selectedId={segment.id} onSelect={selectSegment} />
        {user?.role === "rep" && <TrackRecordInline userId={user.id} />}
      </aside>

      <section
        className="flex min-w-0 flex-col gap-4"
        onKeyDown={(e) => {
          if (e.key !== "Enter" || !(e.ctrlKey || e.metaKey) || action.disabled) return;
          e.preventDefault();
          action.onClick();
        }}
      >
        <Card>
          <CardBody className="flex flex-col gap-4 pt-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h1 className="text-lg font-semibold" data-testid="segment-title">
                  {segment.label}
                </h1>
                <p className="break-words text-xs text-muted">{segment.description}</p>
                {segment.planComment && <p className="mt-1 max-w-3xl text-xs italic text-muted">“{segment.planComment}”</p>}
                {user?.role !== "rep" && (
                  <p className="mt-1 text-[11px] text-muted" data-testid="basis-note">
                    Monthly plan: {BASIS_LABELS[segment.planBasis] ?? segment.planBasis} · last year from{" "}
                    {LAST_YEAR_LABELS[segment.lastYearBasis] ?? "no data"}
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

        <Card className="border-ink/15 shadow-[0_1px_2px_rgb(22_33_26/0.05),0_12px_32px_-16px_rgb(22_33_26/0.25)]">
          <CardBody className="flex flex-col gap-5 pt-5">
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
                <Button size="sm" variant="ghost" onClick={resetToIbp}>
                  Back to the IBP number
                </Button>
              </p>
            )}
            <DemandInstrument impact={live.impact} entry={entry} flags={live.flags} />
            <Checks
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
          </CardBody>
        </Card>

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

        {receipt && <SubmitReceipt entry={receipt} />}

        <section aria-labelledby="impact-title" className="mt-4 flex flex-col gap-4">
          <h2 id="impact-title" className="eyebrow">
            What this number means
          </h2>
          <div className="grid gap-4 md:grid-cols-3">
            <ShareTile impact={live.impact} megaName={cube.megaSegmentDesc} />
            <YtgTile impact={live.impact} />
            <HectaresTile impact={live.impact} />
          </div>
          <VolumePriceBar revenue={live.impact.revenue} money={money} />
        </section>

        {(owns || ownsIbp) && (
          <SubmitBar
            entry={entry}
            onValueChange={(value) => setDraft({ ...draft, value })}
            flags={live.flags}
            blocker={blocker}
            onFixBlocker={onFixBlocker}
            action={action}
          />
        )}
      </section>
    </div>
  );
}
