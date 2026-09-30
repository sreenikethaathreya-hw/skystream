import { CalendarClock, FastForward, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { useAdvanceMonth, useResetDemo } from "@/hooks/mutations";
import { useMeta } from "@/hooks/queries";
import { monthName } from "@/lib/format";

export function DemoControls() {
  const { data: meta } = useMeta();
  const advance = useAdvanceMonth();
  const reset = useResetDemo();
  const toast = useToast();

  const onAdvance = () =>
    advance.mutate(undefined, {
      onSuccess: (r) =>
        toast({
          tone: "success",
          title: `${monthName(r.fromMonth)} closed, actuals are in`,
          body: r.resolved.length
            ? `${r.confirmed} confirmed, ${r.contradicted} contradicted, ${r.inconclusive} inconclusive claims. Track records updated.`
            : "No claims were due this month.",
        }),
      onError: (e) => toast({ tone: "error", title: "Could not advance", body: e.message }),
    });

  const onReset = () =>
    reset.mutate(undefined, {
      onSuccess: () => toast({ tone: "info", title: "Demo reset", body: "Seed data reloaded; the clock is back to the start." }),
    });

  return (
    <div className="flex items-center gap-2">
      <span className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs font-medium tabular">
        <CalendarClock size={14} className="text-muted" />
        {meta ? `${monthName(meta.clock.month)} ${meta.clock.year}` : "..."}
      </span>
      <Button size="sm" variant="secondary" onClick={onAdvance} disabled={advance.isPending} data-testid="advance-month">
        <FastForward size={14} /> {advance.isPending ? "Closing month..." : "Advance month"}
      </Button>
      <Button size="sm" variant="ghost" onClick={onReset} disabled={reset.isPending} title="Reset demo data">
        <RotateCcw size={14} />
      </Button>
    </div>
  );
}
