import { useState, type FormEvent } from "react";
import { Pencil, RefreshCw, Trash2 } from "lucide-react";
import { SourceTable } from "@/components/chat/SourceTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDeleteWidget, useRenameWidget } from "@/hooks/mutations";
import { useWidgetRun } from "@/hooks/queries";
import type { Scope, UserWidget } from "@/lib/types";

function WidgetBody({ id }: { id: number }) {
  const { data, isLoading, error } = useWidgetRun(id);
  if (isLoading) return <Skeleton className="h-24" />;
  if (error || !data) return <p className="text-xs text-crit-700">Could not load this widget. {error?.message}</p>;
  if (data.status === "error") return <p className="text-xs text-muted">{data.error}</p>;
  if (!data.sources.length) return <p className="text-xs text-muted">Nothing to show right now.</p>;
  return (
    <div className="flex flex-col gap-3">
      {data.sources.map((source, index) => (
        <div key={index} className="max-h-72 overflow-auto">
          {data.sources.length > 1 && <p className="mb-1 text-[11px] font-medium text-muted">{source.label}</p>}
          <SourceTable source={source} />
        </div>
      ))}
    </div>
  );
}

function WidgetCard({ widget, scope }: { widget: UserWidget; scope: Scope | null }) {
  const run = useWidgetRun(widget.id);
  const rename = useRenameWidget();
  const remove = useDeleteWidget();
  const [title, setTitle] = useState<string | null>(null);
  const otherScope = !!scope && (scope.countryCode !== widget.countryCode || scope.megaSegmentId !== widget.megaSegmentId);

  const saveTitle = (event: FormEvent) => {
    event.preventDefault();
    if (!title?.trim()) return;
    rename.mutate({ id: widget.id, title: title.trim() }, { onSuccess: () => setTitle(null) });
  };

  return (
    <Card className="flex min-w-0 flex-col" data-testid="custom-widget">
      <div className="flex items-start justify-between gap-2 px-4 pt-3">
        {title === null ? (
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold text-ink">{widget.title}</h3>
            {otherScope && (
              <Badge tone="neutral" className="mt-1">
                {widget.countryCode} · {widget.megaSegmentId}
              </Badge>
            )}
          </div>
        ) : (
          <form onSubmit={saveTitle} className="flex min-w-0 flex-1 items-center gap-1.5">
            <label className="sr-only" htmlFor={`title-${widget.id}`}>
              Widget title
            </label>
            <input
              id={`title-${widget.id}`}
              value={title}
              maxLength={120}
              autoFocus
              onChange={(e) => setTitle(e.target.value)}
              onKeyDown={(e) => e.key === "Escape" && setTitle(null)}
              className="h-7 min-w-0 flex-1 rounded border border-line bg-surface px-2 text-xs text-ink"
            />
            <Button size="sm" type="submit" className="h-7" disabled={!title.trim() || rename.isPending}>
              Save
            </Button>
          </form>
        )}
        {title === null && (
          <div className="flex shrink-0 items-center">
            <Button size="sm" variant="ghost" aria-label="Refresh" onClick={() => run.refetch()} disabled={run.isFetching}>
              <RefreshCw size={14} className={run.isFetching ? "animate-spin" : ""} aria-hidden="true" />
            </Button>
            <Button size="sm" variant="ghost" aria-label="Rename" onClick={() => setTitle(widget.title)}>
              <Pencil size={14} aria-hidden="true" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              aria-label={`Remove ${widget.title}`}
              disabled={remove.isPending}
              onClick={() => remove.mutate(widget.id)}
            >
              <Trash2 size={14} aria-hidden="true" />
            </Button>
          </div>
        )}
      </div>
      <div className="px-4 pb-4 pt-2">
        <WidgetBody id={widget.id} />
      </div>
    </Card>
  );
}

/** Tables the user pinned from the assistant, re-run with fresh data on every view. */
export function MyWidgets({ widgets, scope }: { widgets: UserWidget[]; scope: Scope | null }) {
  if (!widgets.length) return null;
  return (
    <section aria-labelledby="my-widgets-title" className="flex flex-col gap-4">
      <h2 id="my-widgets-title" className="eyebrow">
        My widgets
      </h2>
      <div className="grid gap-4 xl:grid-cols-2">
        {widgets.map((widget) => (
          <WidgetCard key={widget.id} widget={widget} scope={scope} />
        ))}
      </div>
    </section>
  );
}
