import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { fmtNum, humanize } from "@/lib/format";
import type { UploadBatch } from "@/lib/types";

function Stat({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div className="rounded-lg bg-canvas px-3 py-2">
      <p className="text-[11px] text-muted">{label}</p>
      <p className={`font-num tabular text-lg font-semibold ${tone ?? ""}`}>{fmtNum(value)}</p>
    </div>
  );
}

const label = (key: string) => humanize(key.replace(/([A-Z])/g, " $1").toLowerCase());

function render(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ");
  if (value && typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function BatchPreview({
  batch,
  busy,
  onCommit,
  onDiscard,
}: {
  batch: UploadBatch;
  busy: boolean;
  onCommit: () => void;
  onDiscard: () => void;
}) {
  const report = batch.report;
  return (
    <Card data-testid="batch-preview">
      <CardHeader
        title={`${humanize(batch.kind)}: ${batch.filename}`}
        subtitle={`Uploaded by ${batch.uploadedBy}${report.countries?.length ? ` · countries ${report.countries.join(", ")}` : ""}`}
        action={<StatusBadge status={batch.status === "previewed" ? "pending" : batch.status} />}
      />
      <CardBody className="flex flex-col gap-3">
        {report.error && <p className="rounded-lg bg-crit-50 px-3 py-2 text-sm text-crit-700">{report.error}</p>}
        <div className="grid grid-cols-4 gap-2">
          <Stat label="Rows read" value={batch.rowsRead} />
          <Stat label="Accepted" value={batch.accepted} tone="text-brand-700" />
          <Stat label="Rejected" value={batch.rejected} tone={batch.rejected ? "text-crit-700" : undefined} />
          <Stat label="Warnings" value={batch.warnings} tone={batch.warnings ? "text-warn-700" : undefined} />
        </div>
        {!!report.warnings?.length && (
          <div>
            <p className="eyebrow">Warnings</p>
            <ul className="mt-1 flex flex-col gap-1 text-sm">
              {report.warnings.map((w) => (
                <li key={w.message} className="flex justify-between gap-3 rounded bg-warn-50 px-2 py-1 text-warn-700">
                  <span>{w.message}</span>
                  <span className="tabular">{fmtNum(w.count)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {!!report.info && Object.keys(report.info).length > 0 && (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            {Object.entries(report.info).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-2 border-b border-line/60 py-0.5">
                <dt className="text-muted">{label(k)}</dt>
                <dd className="tabular text-right">{render(v)}</dd>
              </div>
            ))}
          </dl>
        )}
        {!!report.rejects?.length && (
          <div>
            <p className="eyebrow">
              Rejected rows {report.rejectsTruncated ? `(first ${report.rejects.length})` : ""}
            </p>
            <div className="mt-1 max-h-56 overflow-auto rounded border border-line">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-canvas text-left">
                  <tr>
                    <th className="px-2 py-1">Row</th>
                    <th className="px-2 py-1">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {report.rejects.map((r, i) => (
                    <tr key={`${r.row}-${i}`} className="border-t border-line/60">
                      <td className="tabular px-2 py-1">{r.row}</td>
                      <td className="px-2 py-1">{r.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        {batch.commitSummary && (
          <p className="rounded-lg bg-brand-50 px-3 py-2 text-xs text-brand-700" data-testid="commit-summary">
            Committed: {Object.entries(batch.commitSummary).map(([k, v]) => `${label(k)} ${render(v)}`).join(" · ")}
          </p>
        )}
        {batch.status === "previewed" && (
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={onDiscard} disabled={busy}>
              Discard
            </Button>
            <Button onClick={onCommit} disabled={busy || batch.accepted === 0} data-testid="commit-upload">
              {busy ? "Working…" : `Commit ${fmtNum(batch.accepted)} rows`}
            </Button>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
