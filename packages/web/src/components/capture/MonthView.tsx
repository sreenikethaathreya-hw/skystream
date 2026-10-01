import { useState } from "react";
import { BarChart3, Table2 } from "lucide-react";
import { MonthChart } from "@/components/capture/MonthChart";
import { MonthGrid } from "@/components/capture/MonthGrid";
import type { SegmentCube } from "@/lib/types";
import { cn } from "@/lib/utils";

type View = "chart" | "table";
const VIEW_KEY = "skystream.monthView";

function readView(): View {
  try {
    return localStorage.getItem(VIEW_KEY) === "table" ? "table" : "chart";
  } catch {
    return "chart";
  }
}

const OPTIONS: { view: View; label: string; icon: typeof BarChart3 }[] = [
  { view: "chart", label: "Chart", icon: BarChart3 },
  { view: "table", label: "Table", icon: Table2 },
];

/** The year at a glance: a chart by default, the exact figures one click away. Both select the month to enter. */
export function MonthView(props: {
  segment: SegmentCube;
  selectedMonth: number;
  draftValue: number;
  onSelect: (month: number) => void;
}) {
  const [view, setView] = useState<View>(readView);

  const choose = (next: View) => {
    setView(next);
    try {
      localStorage.setItem(VIEW_KEY, next);
    } catch {
      // Private windows can refuse storage; the choice still applies for this visit.
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <h2 className="eyebrow">Year at a glance · thousand seeds</h2>
        <div role="radiogroup" aria-label="Show months as" className="inline-flex rounded-lg border border-line bg-canvas p-0.5">
          {OPTIONS.map(({ view: option, label, icon: Icon }) => (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={view === option}
              onClick={() => choose(option)}
              data-testid={`month-view-${option}`}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium",
                view === option ? "bg-surface text-ink shadow-sm" : "text-muted hover:text-ink",
              )}
            >
              <Icon size={13} aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>
      </div>
      {view === "chart" ? <MonthChart {...props} /> : <MonthGrid {...props} />}
    </div>
  );
}
