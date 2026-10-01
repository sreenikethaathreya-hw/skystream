import { CalendarClock, FastForward, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfirmButton } from "@/components/ui/confirm-button";
import { useToast } from "@/components/ui/toast";
import { useAdvanceMonth, useResetDemo } from "@/hooks/mutations";
import { useMeta } from "@/hooks/queries";
import { monthName } from "@/lib/format";

const ON_DARK = "h-7 whitespace-nowrap text-white/80 hover:bg-white/10 hover:text-white";

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
    <div className="flex items-center gap-1">
      <span className="tabular inline-flex items-center gap-1.5 whitespace-nowrap px-1 font-medium text-white">
        <CalendarClock size={13} className="text-white/55" aria-hidden="true" />
        {monthName(meta.clock.month)} {meta.clock.year}
      </span>
      <Button
        size="sm"
        variant="ghost"
        className={ON_DARK}
        onClick={onAdvance}
        disabled={advance.isPending}
        data-testid="advance-month"
      >
        <FastForward size={14} aria-hidden="true" /> Advance month
      </Button>
      <ConfirmButton
        size="sm"
        variant="ghost"
        className={ON_DARK}
        onConfirm={onReset}
        confirmLabel="Reset demo?"
        disabled={reset.isPending}
        title="Reset demo data"
        aria-label="Reset demo data"
      >
        <RotateCcw size={14} aria-hidden="true" />
      </ConfirmButton>
    </div>
  );
}
