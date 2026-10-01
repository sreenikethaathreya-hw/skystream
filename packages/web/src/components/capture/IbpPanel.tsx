import type { ReactNode } from "react";
import { Boxes } from "lucide-react";
import { StatusBadge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { fmtKs, monthName } from "@/lib/format";
import type { IbpMonth } from "@/lib/types";

/** The rep's number as committed in IBP. It is read-only here: change it in IBP, justify it in Skystream. */
export function IbpPanel({ month, ibp, ask }: { month: number; ibp: IbpMonth | undefined; ask?: ReactNode }) {
  if (!ibp) {
    return (
      <Card data-testid="ibp-panel">
        <CardBody className="pt-4 text-sm text-muted">
          No IBP number for {monthName(month)} yet. It arrives with the next SAC upload; until then the figures below
          show the plan.
        </CardBody>
      </Card>
    );
  }
  return (
    <Card data-testid="ibp-panel">
      <CardHeader
        title={`Committed in IBP: ${fmtKs(ibp.qtyKs)}`}
        subtitle={`${monthName(month)} · snapshot ${ibp.snapshot} · change the number in IBP, justify it here`}
        icon={<Boxes size={15} />}
        action={
          ibp.entryStatus || ask ? (
            <span className="flex items-center gap-1">
              {ask}
              {ibp.entryStatus && <StatusBadge status={ibp.entryStatus} />}
            </span>
          ) : undefined
        }
      />
      <CardBody>
        <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-xs" data-testid="ibp-varieties">
          {ibp.varieties.map((v) => (
            <div key={v.variety} className="contents">
              <dt className="text-muted">{v.variety}</dt>
              <dd className="tabular text-right">{fmtKs(v.qtyKs)}</dd>
            </div>
          ))}
        </dl>
      </CardBody>
    </Card>
  );
}
