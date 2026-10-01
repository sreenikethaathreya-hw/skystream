import type { ReactNode } from "react";
import { BaselinePanel } from "@/components/capture/BaselinePanel";
import { HectaresTile, ShareTile, YtgTile } from "@/components/capture/ImpactTiles";
import { VolumePriceBar } from "@/components/capture/VolumePriceBar";
import { TrackRecordInline } from "@/components/reps/TrackRecordInline";
import type { Impact } from "@/lib/mathTypes";
import type { Money } from "@/lib/money";
import type { Cube, Role, SegmentCube } from "@/lib/types";

export interface CaptureWidgetProps {
  cube: Cube;
  segment: SegmentCube;
  impact: Impact;
  month: number;
  value: number;
  money: Money;
  userId: string;
}

/** Where a widget sits on Capture: context above the number, impact below submit, aside under the segment list. */
export type WidgetSlot = "context" | "impact" | "aside";

export interface CaptureWidget {
  id: string;
  title: string;
  description: string;
  slot: WidgetSlot;
  /** Spans the full impact row instead of one tile column. */
  wide?: boolean;
  roles?: Role[];
  render: (props: CaptureWidgetProps) => ReactNode;
}

/**
 * Built-in Capture widgets. Every one starts hidden; each user adds the ones they need under Customize.
 * The capture core (month grid, number, checks, reason, submit) is never a widget.
 */
export const CAPTURE_WIDGETS: CaptureWidget[] = [
  {
    id: "baseline",
    title: "Baseline and benchmarks",
    description: "Share history, last year, the month's historical average and grower potential.",
    slot: "context",
    render: (p) => (
      <BaselinePanel ctx={p.segment.context} impact={p.impact} month={p.month} value={p.value} megaName={p.cube.megaSegmentDesc} />
    ),
  },
  {
    id: "share",
    title: "Market share",
    description: "Full-year volume share with your range, and the competitors that move.",
    slot: "impact",
    render: (p) => <ShareTile impact={p.impact} megaName={p.cube.megaSegmentDesc} />,
  },
  {
    id: "ytg",
    title: "Year to go",
    description: "What is left to sell this year and the gap to plan.",
    slot: "impact",
    render: (p) => <YtgTile impact={p.impact} />,
  },
  {
    id: "hectares",
    title: "Implied hectares",
    description: "The planted area your number implies, against the market.",
    slot: "impact",
    render: (p) => <HectaresTile impact={p.impact} />,
  },
  {
    id: "volume_price",
    title: "Volume and price",
    description: "How much of the revenue change comes from volume and how much from price.",
    slot: "impact",
    wide: true,
    render: (p) => <VolumePriceBar revenue={p.impact.revenue} money={p.money} />,
  },
  {
    id: "track_record",
    title: "My track record",
    description: "How your past claims resolved against actuals.",
    slot: "aside",
    roles: ["rep"],
    render: (p) => <TrackRecordInline userId={p.userId} />,
  },
];

export function widgetsFor(role: Role | undefined): CaptureWidget[] {
  return CAPTURE_WIDGETS.filter((w) => !w.roles || (role !== undefined && w.roles.includes(role)));
}

/** The user's visible widgets for one slot, in the order they added them. */
export function visibleIn(slot: WidgetSlot, visible: string[], role: Role | undefined): CaptureWidget[] {
  const available = new Map(widgetsFor(role).map((w) => [w.id, w]));
  return visible.map((id) => available.get(id)).filter((w): w is CaptureWidget => !!w && w.slot === slot);
}
