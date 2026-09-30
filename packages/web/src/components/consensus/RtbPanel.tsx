import { useState } from "react";
import { FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { useDraftRtb } from "@/hooks/mutations";
import type { SegmentCube } from "@/lib/types";

export function RtbPanel({ segments }: { segments: SegmentCube[] }) {
  const [segmentId, setSegmentId] = useState<number>(segments.find((s) => s.id === 2482)?.id ?? segments[0]?.id);
  const draft = useDraftRtb();
  return (
    <Card>
      <CardHeader
        title="Reasons to believe"
        subtitle="Drafted from confirmed claims, market notes and competitor trends only"
        icon={<FileText size={15} />}
      />
      <CardBody className="flex flex-col gap-3">
        <div className="flex gap-2">
          <select
            aria-label="RTB segment"
            className="h-9 flex-1 rounded-lg border border-line bg-surface px-2 text-sm"
            value={segmentId}
            onChange={(e) => setSegmentId(Number(e.target.value))}
          >
            {segments.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
          <Button variant="secondary" onClick={() => draft.mutate(segmentId)} disabled={draft.isPending} data-testid="draft-rtb">
            {draft.isPending ? "Drafting..." : "Draft RTB"}
          </Button>
        </div>
        {draft.data && (
          <div data-testid="rtb-text">
            <pre className="whitespace-pre-wrap rounded-lg bg-canvas p-3 font-sans text-sm leading-relaxed">{draft.data.text}</pre>
            <p className="mt-1 flex items-center gap-2 text-[11px] text-muted">
              <Badge tone={draft.data.provider === "gemini" ? "jev" : "neutral"}>{draft.data.provider}</Badge>
              cites {draft.data.citedEntryIds.length} confirmed claims
            </p>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
