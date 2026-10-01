import type { ReactNode } from "react";
import { Sparkles } from "lucide-react";
import { ClaimTags } from "@/components/claims/ClaimTags";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import type { StructuredClaim } from "@/lib/types";

const MAX_LENGTH = 600;
const COUNTER_FROM = 480;

const FIELD_NAMES: Record<string, string> = {
  driver: "driver",
  direction: "direction",
  competitor: "competitor",
  variety: "variety",
  magnitude: "size of the effect",
  specificity: "specificity",
};

export function JustificationBox({
  text,
  required,
  claim,
  stale,
  analyzing,
  onChange,
  onAnalyze,
  ask,
}: {
  text: string;
  required: boolean;
  claim: StructuredClaim | null;
  stale: boolean;
  analyzing: boolean;
  onChange: (text: string) => void;
  onAnalyze: () => void;
  ask?: ReactNode;
}) {
  const weakAddress = claim?.addressesFlags != null && claim.addressesFlags < 0.5;
  return (
    <Card>
      <CardHeader
        title={
          <span>
            Why this number? {required && <span className="text-crit-700">(required)</span>}
          </span>
        }
        subtitle="One sentence. It is checked against next month's actuals."
        icon={<Sparkles size={15} />}
        action={ask}
      />
      <CardBody className="flex flex-col gap-3">
        <div className="flex gap-2">
          <div className="flex flex-1 flex-col gap-1">
            <textarea
              value={text}
              onChange={(e) => onChange(e.target.value)}
              rows={2}
              maxLength={MAX_LENGTH}
              id="justification"
              name="justification"
              aria-label="Why this number"
              data-testid="justification-input"
              placeholder="e.g. Two Almeria cooperatives are switching from Sur Seeds to Leontes…"
              className="resize-none rounded-lg border border-line bg-surface px-3 py-2 text-sm"
            />
            {text.length >= COUNTER_FROM && (
              <span className="tabular self-end text-[11px] text-muted">
                {text.length}/{MAX_LENGTH}
              </span>
            )}
          </div>
          <Button variant="jev" onClick={onAnalyze} disabled={!text.trim() || analyzing} data-testid="structure-button">
            {analyzing ? "Checking…" : "Check my reason"}
          </Button>
        </div>
        {claim && (
          <div className={stale ? "opacity-50" : undefined} aria-live="polite">
            <p className="mb-2 rounded-lg bg-canvas px-3 py-2 text-sm" data-testid="claim-summary">
              <span className="font-medium">Reads as: </span>
              {claim.summary}
            </p>
            <ClaimTags decisions={claim.decisions} provider={claim.provider} latencyMs={claim.latencyMs} />
            {claim.mismatches.map((m) => (
              <p key={m.code} className="mt-2 text-xs text-crit-700" data-testid={`mismatch-${m.code}`}>
                {m.message}
              </p>
            ))}
            {claim.lowConfidenceFields.length > 0 && (
              <p className="mt-2 text-xs text-warn-700" data-testid="low-confidence">
                Not clear on the {claim.lowConfidenceFields.map((f) => FIELD_NAMES[f] ?? f).join(", ")}. Name the
                competitor, variety or customer, and say how big the effect is.
              </p>
            )}
            {weakAddress && (
              <p className="mt-1 text-xs text-crit-700">
                This sentence does not explain the flags. Be more specific about why the number is still right.
              </p>
            )}
            {stale && <p className="mt-1 text-xs text-muted">Numbers changed since the check; it re-runs on submit.</p>}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
