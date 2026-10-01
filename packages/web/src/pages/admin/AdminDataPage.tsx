import { useState } from "react";
import { Download, Upload } from "lucide-react";
import { BatchPreview } from "@/components/admin/BatchPreview";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { useBatchAction, useUpload } from "@/hooks/mutations";
import { useUploadKinds, useUploads } from "@/hooks/queries";
import { useSession } from "@/hooks/useSession";
import { api } from "@/lib/api";
import { fmtDate, fmtDateTime, fmtNum } from "@/lib/format";
import type { UploadBatch } from "@/lib/types";

export function AdminDataPage() {
  const { user, dataMode } = useSession();
  const { data: kinds = [] } = useUploadKinds();
  const { data: history = [] } = useUploads();
  const upload = useUpload();
  const action = useBatchAction();
  const toast = useToast();
  const [kind, setKind] = useState("hierarchy");
  const [file, setFile] = useState<File | null>(null);
  const [current, setCurrent] = useState<UploadBatch | null>(null);

  if (user?.role !== "admin") return <p className="text-sm text-muted">Only admins can load data.</p>;

  const onUpload = () =>
    file &&
    upload.mutate(
      { kind, file },
      {
        onSuccess: (b) => setCurrent(b),
        onError: (e) => toast({ tone: "error", title: "Upload failed", body: e.message }),
      },
    );

  const act = (verb: "commit" | "discard") =>
    current &&
    action.mutate(
      { id: current.id, action: verb },
      {
        onSuccess: (b) => {
          setCurrent(b);
          if (verb === "commit") {
            const resolved = b.commitSummary?.claimsResolved as number | undefined;
            toast({
              tone: "success",
              title: `${b.filename} committed`,
              body: resolved !== undefined ? `${resolved} claims resolved against the new actuals.` : undefined,
            });
          }
        },
        onError: (e) => toast({ tone: "error", title: `Could not ${verb}`, body: e.message }),
      },
    );

  const selected = kinds.find((k) => k.kind === kind);

  return (
    <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
      <aside className="flex flex-col gap-4">
        <Card>
          <CardHeader title="Upload a file" subtitle="Validated first; nothing changes until you commit." icon={<Upload size={15} />} />
          <CardBody className="flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-xs text-muted">
              What is it?
              <select
                aria-label="Upload kind"
                className="h-9 rounded-lg border border-line bg-surface px-2 text-sm text-ink"
                value={kind}
                onChange={(e) => setKind(e.target.value)}
              >
                {kinds.map((k) => (
                  <option key={k.kind} value={k.kind}>
                    {k.label}
                    {k.required ? "" : " (optional)"}
                  </option>
                ))}
              </select>
            </label>
            {selected && <p className="text-xs text-muted">Source: {selected.source}</p>}
            <input
              type="file"
              accept=".xlsx,.xlsm,.xls,.csv"
              aria-label="File"
              data-testid="upload-file"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="text-sm"
            />
            <Button onClick={onUpload} disabled={!file || upload.isPending} data-testid="upload-button">
              {upload.isPending ? "Validating…" : "Upload and preview"}
            </Button>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Load order and status"
            subtitle={
              dataMode === "demo"
                ? "Demo figures are preloaded from the seed; uploads here add to or replace them."
                : "Upload the hierarchy first; every figure is keyed on it."
            }
          />
          <CardBody className="flex flex-col gap-2">
            {kinds.map((k, i) => (
              <div key={k.kind} className="flex items-center justify-between gap-2 text-sm">
                <span>
                  {i + 1}. {k.label} {!k.required && <Badge>optional</Badge>}
                </span>
                <span className="flex items-center gap-2">
                  {k.lastCommittedAt ? (
                    <Badge tone="brand">{fmtDate(k.lastCommittedAt)}</Badge>
                  ) : (
                    <Badge tone={k.required ? "warn" : "neutral"}>not loaded</Badge>
                  )}
                  {k.template && (
                    <button
                      title="Download template"
                      aria-label={`Download ${k.label} template`}
                      className="rounded text-muted hover:text-ink"
                      onClick={() => void api.download(`/admin/templates/${k.kind}.csv`, `${k.kind}-template.csv`)}
                    >
                      <Download size={14} aria-hidden="true" />
                    </button>
                  )}
                </span>
              </div>
            ))}
          </CardBody>
        </Card>
      </aside>

      <section className="flex flex-col gap-4">
        {current ? (
          <BatchPreview batch={current} busy={action.isPending} onCommit={() => act("commit")} onDiscard={() => act("discard")} />
        ) : (
          <Card>
            <CardBody className="pt-4 text-sm text-muted">Upload a file to see what will be loaded, rejected and why.</CardBody>
          </Card>
        )}
        <Card>
          <CardHeader title="Upload history" />
          <CardBody>
            <table className="w-full text-sm" data-testid="upload-history">
              <thead className="text-left text-xs text-muted">
                <tr>
                  <th className="py-1">When</th>
                  <th>Kind</th>
                  <th>File</th>
                  <th>Status</th>
                  <th className="text-right">Accepted</th>
                  <th className="text-right">Rejected</th>
                </tr>
              </thead>
              <tbody>
                {history.map((b) => (
                  <tr key={b.id} className="border-t border-line/60 hover:bg-canvas">
                    <td className="py-1 text-xs">{fmtDateTime(b.createdAt)}</td>
                    <td>{b.kind}</td>
                    <td className="max-w-56 truncate">
                      <button
                        type="button"
                        className="max-w-full truncate rounded text-left text-brand-700 hover:underline"
                        onClick={() => setCurrent(b)}
                      >
                        {b.filename}
                      </button>
                    </td>
                    <td>
                      <StatusBadge status={b.status === "previewed" ? "pending" : b.status} />
                    </td>
                    <td className="tabular text-right">{fmtNum(b.accepted)}</td>
                    <td className="tabular text-right">{fmtNum(b.rejected)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>
      </section>
    </div>
  );
}
