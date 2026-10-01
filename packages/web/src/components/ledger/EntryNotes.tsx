import { useState } from "react";
import { MessageCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { useAddNote } from "@/hooks/mutations";
import type { EntryNote } from "@/lib/types";

/** The lead's questions and the rep's answers on one entry, with a box to add one. */
export function EntryNotes({ entryId, notes, canWrite }: { entryId: string; notes: EntryNote[]; canWrite: boolean }) {
  const [text, setText] = useState("");
  const add = useAddNote();
  const toast = useToast();
  if (!notes.length && !canWrite) return null;
  const submit = () =>
    add.mutate(
      { entryId, body: text.trim() },
      {
        onSuccess: () => setText(""),
        onError: (e) => toast({ tone: "error", title: "Could not add the note", body: e.message }),
      },
    );
  return (
    <div className="flex flex-col gap-1.5 rounded-lg border border-line px-3 py-2" data-testid="entry-notes">
      <p className="flex items-center gap-1 text-xs font-medium text-muted">
        <MessageCircle size={12} /> Notes
      </p>
      {notes.map((n) => (
        <p key={n.id} className="text-xs" data-testid="entry-note">
          <span className="font-medium">{n.userName}</span>
          <span className="text-muted"> · {new Date(n.createdAt).toLocaleString()}</span>
          {n.via === "chat" && (
            <Badge className="ml-1" tone="neutral">
              via assistant
            </Badge>
          )}
          <span className="block whitespace-pre-wrap">{n.body}</span>
        </p>
      ))}
      {canWrite && (
        <div className="flex gap-2">
          <input
            aria-label="Add a note"
            className="h-8 min-w-0 flex-1 rounded-lg border border-line bg-surface px-2 text-xs"
            maxLength={600}
            placeholder="Ask or answer about this entry"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && text.trim()) submit();
            }}
          />
          <Button size="sm" variant="secondary" disabled={!text.trim() || add.isPending} onClick={submit}>
            Add note
          </Button>
        </div>
      )}
    </div>
  );
}
