import { useCallback, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { DraftNumbers } from "@/components/capture/EntryPanel";
import { computeImpact } from "@/lib/demandMath";
import { evaluateFlags } from "@/lib/flags";
import { evaluateRules } from "@/lib/leadRules";
import type { EntryInput } from "@/lib/mathTypes";
import type { Cube, SegmentCube } from "@/lib/types";

const DEFAULT_SPREAD = 0.08;
const EMPTY_DRAFT: DraftNumbers = { value: 0, lowPct: DEFAULT_SPREAD, highPct: DEFAULT_SPREAD, price: null };

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

interface Edit {
  key: string;
  draft: DraftNumbers;
  dirty: boolean;
}

interface Cell {
  segment?: number;
  month?: number;
}

/**
 * Segment and month are mirrored to the URL so the view can be shared; the typed draft is kept per cell so a cube
 * refetch never resets it. State is the source of truth because router updates land in a transition, which would let
 * a fast keystroke reach the previous cell.
 */
export function useCaptureDraft(cube: Cube | undefined, preferredSegmentId: number | undefined) {
  const [params, setParams] = useSearchParams();
  const [cell, setCell] = useState<Cell>(() => ({
    segment: Number(params.get("segment")) || undefined,
    month: Number(params.get("month")) || undefined,
  }));
  const requestedSegment = cell.segment;
  const requestedMonth = cell.month;

  const segments = cube?.segments;
  const segment =
    segments?.find((s) => s.id === requestedSegment) ?? segments?.find((s) => s.id === preferredSegmentId) ?? segments?.[0];
  const clockMonth = cube?.clockMonth ?? 1;
  const month = Math.min(12, Math.max(requestedMonth ?? clockMonth, clockMonth));
  const key = segment ? `${segment.id}|${month}` : "";

  const [edit, setEdit] = useState<Edit | null>(null);
  const initial = useMemo(() => (segment ? initialDraft(segment, month) : EMPTY_DRAFT), [segment, month]);
  const draft = edit?.key === key ? edit.draft : initial;
  const dirty = edit?.key === key && edit.dirty;

  const setParam = useCallback(
    (name: keyof Cell, value: number) => {
      setCell((c) => ({ ...c, [name]: value }));
      setParams(
        (current) => {
          const next = new URLSearchParams(current);
          next.set(name, String(value));
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );
  const selectSegment = useCallback((id: number) => setParam("segment", id), [setParam]);
  const setMonth = useCallback((m: number) => setParam("month", m), [setParam]);
  const setDraft = useCallback((next: DraftNumbers) => setEdit({ key, draft: next, dirty: true }), [key]);
  const markSaved = useCallback(() => setEdit((e) => e && { ...e, dirty: false }), []);

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

  return { segment, month, setMonth, draft, setDraft, dirty, markSaved, entry, live, selectSegment };
}
