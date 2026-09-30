import { CalendarClock, FastForward, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { useAdvanceMonth, useResetDemo } from "@/hooks/mutations";
import { useMeta } from "@/hooks/queries";
import { monthName } from "@/lib/format";

/** Demo mode only: a simulated calendar. Real mode closes a month when its actuals are uploaded. */
export function DemoControls() {
  const { data: meta } = useMeta();
  const advance = useAdvanceMonth();
  const reset = useResetDemo();
  const toast = useToast();
  if (!meta?.clock) return null;

  const onAdvance = () =>
    advance.mutate(undefined, {
      onSuccess: (r) =>
        toast({
          tone: "success",
          title: `${monthName(r.fromMonth)} closed, clock now ${monthName(r.toMonth)}`,
          body: r.resolved.length
            ? `${r.confirmed} confirmed, ${r.contradicted} contradicted, ${r.inconclusive} inconclusive claims resolved against ${monthName(r.fromMonth)} actuals.`
            : "No claims were due this month.",
        }),
      onError: (e) => toast({ tone: "error", title: "Could not advance", body: e.message }),
    });

  const onReset = () =>
    reset.mutate(undefined, { onSuccess: () => toast({ tone: "info", title: "Demo reset to seed data" }) });

  return (
    <div className="flex items-center gap-2">
      <span className="tabular inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg border border-line bg-surface px-2.5 py-1 text-xs font-medium">
        <CalendarClock size={13} className="text-muted" />
        {monthName(meta.clock.month)} {meta.clock.year}
      </span>
      <Button size="sm" variant="secondary" className="whitespace-nowrap" onClick={onAdvance}
        disabled={advance.isPending} data-testid="advance-month">
        <FastForward size={14} /> Advance month
      </Button>
      <Button size="sm" variant="ghost" onClick={onReset} disabled={reset.isPending} title="Reset demo data">
        <RotateCcw size={14} />
      </Button>
    </div>
  );
}
