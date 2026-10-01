import { useState, type FormEvent } from "react";
import { NavLink } from "react-router-dom";
import { ArrowUpRight, Pin } from "lucide-react";
import { SourceTable } from "@/components/chat/SourceTable";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { usePinWidget } from "@/hooks/mutations";
import { useScope } from "@/hooks/useScope";
import type { ChatLink, ChatSource } from "@/lib/types";

/** Saves a table as a Capture widget: the tool and its arguments, re-run fresh on every view. */
function PinControl({ source }: { source: ChatSource }) {
  const { scope } = useScope();
  const pin = usePinWidget();
  const toast = useToast();
  const [title, setTitle] = useState<string | null>(null);
  if (!scope || !source.args) return null;

  if (pin.isSuccess) {
    return <span className="text-[11px] font-medium text-brand-700">Pinned to Capture</span>;
  }
  if (title === null) {
    return (
      <button
        type="button"
        onClick={() => setTitle(source.label)}
        className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium text-brand-700 hover:bg-brand-50"
        data-testid="pin-source"
      >
        <Pin size={12} aria-hidden="true" />
        Pin as widget
      </button>
    );
  }

  const save = (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim() || !source.args) return;
    pin.mutate(
      { title: title.trim(), tool: source.tool, args: source.args, ...scope },
      {
        onSuccess: () => toast({ tone: "success", title: "Pinned to Capture", body: "It shows under My widgets." }),
        onError: (e) => toast({ tone: "error", title: "Could not pin the table", body: e.message }),
      },
    );
  };

  return (
    <form onSubmit={save} className="flex items-center gap-1.5" data-testid="pin-form">
      <label className="sr-only" htmlFor={`pin-${source.tool}`}>
        Widget title
      </label>
      <input
        id={`pin-${source.tool}`}
        value={title}
        maxLength={120}
        onChange={(e) => setTitle(e.target.value)}
        className="h-7 w-48 rounded border border-line bg-surface px-2 text-xs text-ink"
        data-autofocus
      />
      <Button size="sm" type="submit" className="h-7" disabled={!title.trim() || pin.isPending}>
        {pin.isPending ? "Pinning…" : "Pin"}
      </Button>
      <Button size="sm" variant="ghost" type="button" className="h-7" onClick={() => setTitle(null)}>
        Cancel
      </Button>
    </form>
  );
}

export function ChatSources({ sources, links }: { sources: ChatSource[]; links: ChatLink[] }) {
  if (!sources.length && !links.length) return null;
  return (
    <div className="mt-2 space-y-2">
      {sources.map((source, index) => (
        <details
          key={`${source.tool}-${index}`}
          className="rounded-lg border border-line bg-canvas/60"
          open={index === 0}
          data-testid="chat-source"
        >
          <summary className="cursor-pointer px-3 py-1.5 text-xs font-medium text-ink">{source.label}</summary>
          <div className="max-h-64 overflow-auto px-3 pb-2">
            <SourceTable source={source} />
          </div>
          {source.pinnable && (
            <div className="border-t border-line/60 px-3 py-1.5">
              <PinControl source={source} />
            </div>
          )}
        </details>
      ))}
      {links.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {links
            .filter((link) => link.to.startsWith("/") && !link.to.startsWith("//"))
            .map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className="inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline"
              >
                {link.label}
                <ArrowUpRight size={12} aria-hidden="true" />
              </NavLink>
            ))}
        </div>
      )}
    </div>
  );
}
