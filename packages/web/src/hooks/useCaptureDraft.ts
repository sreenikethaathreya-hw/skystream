import { useCallback, useEffect, useMemo, useState } from "react";
import type { DraftNumbers } from "@/components/capture/EntryPanel";
import { computeImpact } from "@/lib/demandMath";
import { evaluateFlags } from "@/lib/flags";
import { evaluateRules } from "@/lib/leadRules";
import type { EntryInput } from "@/lib/mathTypes";
import type { Cube, SegmentCube } from "@/lib/types";

const DEFAULT_SPREAD = 0.08;

function initialDraft(segment: SegmentCube, month: number): DraftNumbers {
  const existing = segment.latestEntries.find((e) => e.month === month);
  if (existing && existing.value > 0) {
    return {
      value: existing.value,
      lowPct: 1 - existing.low / existing.value,
      highPct: existing.high / existing.value - 1,
      price: null,
    };
  }
  return { value: Math.round(segment.context.monthlyPlan[month - 1]), lowPct: DEFAULT_SPREAD, highPct: DEFAULT_SPREAD, price: null };
}

export function useCaptureDraft(cube: Cube | undefined, preferredSegmentId: number | undefined) {
  const [segmentId, setSegmentId] = useState<number | undefined>(preferredSegmentId);
  const [month, setMonth] = useState<number>(cube?.clockMonth ?? 1);
  const [draft, setDraft] = useState<DraftNumbers>({ value: 0, lowPct: DEFAULT_SPREAD, highPct: DEFAULT_SPREAD, price: null });

  const segment = cube?.segments.find((s) => s.id === segmentId) ?? cube?.segments[0];

  const scopeKey = cube ? `${cube.countryCode}|${cube.megaSegmentId}` : "";
  useEffect(() => {
    setSegmentId(preferredSegmentId);
    // Pick the rep's own segment again whenever the scope changes, not on every refetch.
  }, [scopeKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!segmentId && preferredSegmentId) setSegmentId(preferredSegmentId);
  }, [preferredSegmentId, segmentId]);

  useEffect(() => {
    if (cube && month < cube.clockMonth) setMonth(Math.min(cube.clockMonth, 12));
  }, [cube, month]);

  useEffect(() => {
    if (segment) setDraft(initialDraft(segment, Math.max(month, segment.context.clockMonth)));
    // Reset only when the target cell changes, not on every cube refetch, so a typed number survives a submit.
  }, [segment?.id, month, segment?.context.clockMonth]);

  const entry: EntryInput = useMemo(
    () => ({
      month,
      value: draft.value,
      low: Math.round(draft.value * (1 - draft.lowPct)),
      high: Math.round(draft.value * (1 + draft.highPct)),
      price: draft.price,
    }),
    [month, draft],
  );

  const live = useMemo(() => {
    if (!segment || !cube) return undefined;
    const impact = computeImpact(segment.context, entry, cube.thresholds);
    return {
      impact,
      flags: [
        ...evaluateFlags(segment.context, entry, impact, cube.thresholds),
        ...evaluateRules(segment.context, segment.id, entry, impact, cube.rules ?? []),
      ],
    };
  }, [segment, cube, entry]);

  const selectSegment = useCallback((id: number) => setSegmentId(id), []);

  return { segment, month, setMonth, draft, setDraft, entry, live, selectSegment };
}
