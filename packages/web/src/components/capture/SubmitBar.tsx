import { DemandField } from "@/components/capture/DemandField";
import { Button } from "@/components/ui/button";
import { fmtNum, monthName } from "@/lib/format";
import type { EntryInput, Flag } from "@/lib/mathTypes";
import { cn } from "@/lib/utils";

const MOD_KEY = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.userAgent) ? "⌘" : "Ctrl";

export interface SubmitAction {
  label: string;
  onClick: () => void;
  disabled: boolean;
  testId: string;
}

/**
 * Pinned to the bottom of the viewport while scrolling the capture page, so the action and a summary of what will be
 * recorded stay in reach. Sticky (not fixed) so it settles at the end of the page instead of covering the last section.
 */
export function SubmitBar({
  entry,
  onValueChange,
  flags,
  blocker,
  onFixBlocker,
  action,
}: {
  entry: EntryInput;
  onValueChange: (value: number) => void;
  flags: Flag[];
  blocker: string | null;
  onFixBlocker?: () => void;
  action: SubmitAction;
}) {
  const critical = flags.some((f) => f.severity === "critical");
  return (
    <div className="sticky bottom-0 z-20 pb-3 pt-2">
      <div
        role="region"
        aria-label="Submit"
        className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-ink/15 bg-surface/95 px-4 py-2.5 shadow-[0_-6px_24px_-14px_rgb(22_33_26/0.35)] backdrop-blur"
      >
        <div className="tabular flex items-center gap-2">
          <span className="eyebrow">{monthName(entry.month)}</span>
          <DemandField
            size="compact"
            value={entry.value}
            onChange={onValueChange}
            label={`${monthName(entry.month)} demand`}
            testId="bar-demand-input"
          />
          <span className="text-xs text-muted">
            {fmtNum(entry.low)}–{fmtNum(entry.high)}
          </span>
        </div>
        <span className={cn("text-xs font-medium", !flags.length ? "text-brand-700" : critical ? "text-crit-700" : "text-warn-700")}>
          {flags.length ? `${flags.length} check${flags.length > 1 ? "s" : ""}` : "No flags"}
        </span>
        <p role="status" className="text-xs">
          {blocker &&
            (onFixBlocker ? (
              <button type="button" onClick={onFixBlocker} className="text-crit-700 underline underline-offset-2">
                {blocker}
              </button>
            ) : (
              <span className="text-muted">{blocker}</span>
            ))}
        </p>
        <div className="ml-auto flex items-center gap-3">
          <kbd className="hidden font-mono text-[11px] text-muted sm:inline">{MOD_KEY}+Enter</kbd>
          <Button onClick={action.onClick} disabled={action.disabled} data-testid={action.testId}>
            {action.label}
          </Button>
        </div>
      </div>
    </div>
  );
}
