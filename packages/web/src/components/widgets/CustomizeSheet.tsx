import { Pin, Trash2 } from "lucide-react";
import { widgetsFor } from "@/components/widgets/registry";
import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { useDeleteWidget, useSaveWidgetPrefs } from "@/hooks/mutations";
import type { Role, UserWidget } from "@/lib/types";

export function CustomizeSheet({
  open,
  onClose,
  role,
  visible,
  custom,
}: {
  open: boolean;
  onClose: () => void;
  role: Role | undefined;
  visible: string[];
  custom: UserWidget[];
}) {
  const save = useSaveWidgetPrefs();
  const remove = useDeleteWidget();
  const shown = new Set(visible);

  // Added widgets go to the end, so the page keeps the order the user built it in.
  const toggle = (id: string) => save.mutate(shown.has(id) ? visible.filter((v) => v !== id) : [...visible, id]);

  return (
    <Sheet open={open} onClose={onClose} title="Customize Capture">
      <div className="flex flex-1 flex-col gap-6 overflow-y-auto p-4">
        <section aria-labelledby="builtin-title" className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <h3 id="builtin-title" className="eyebrow">
              Widgets
            </h3>
            {visible.length > 0 && (
              <Button size="sm" variant="ghost" onClick={() => save.mutate([])} data-testid="hide-all-widgets">
                Hide all
              </Button>
            )}
          </div>
          <p className="text-xs text-muted">Everything starts hidden. Add what you need; it is saved to your account.</p>
          <ul className="flex flex-col gap-2">
            {widgetsFor(role).map((widget) => (
              <li key={widget.id}>
                <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-line p-3 hover:bg-canvas">
                  <input
                    type="checkbox"
                    className="mt-0.5 size-4 accent-brand-600"
                    checked={shown.has(widget.id)}
                    onChange={() => toggle(widget.id)}
                    data-testid={`widget-toggle-${widget.id}`}
                  />
                  <span className="flex flex-col">
                    <span className="text-sm font-medium text-ink">{widget.title}</span>
                    <span className="text-xs text-muted">{widget.description}</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="pinned-title" className="flex flex-col gap-2">
          <h3 id="pinned-title" className="eyebrow">
            My widgets
          </h3>
          {custom.length === 0 ? (
            <p className="flex items-start gap-2 rounded-lg bg-canvas p-3 text-xs text-muted">
              <Pin size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
              Ask the assistant a question, then use “Pin as widget” under its table. It shows here and on Capture, with
              fresh data every time.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {custom.map((widget) => (
                <li key={widget.id} className="flex items-center justify-between gap-3 rounded-lg border border-line p-3">
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium text-ink">{widget.title}</span>
                    <span className="text-xs text-muted">
                      {widget.countryCode} · {widget.megaSegmentId}
                    </span>
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`Remove ${widget.title}`}
                    disabled={remove.isPending}
                    onClick={() => remove.mutate(widget.id)}
                  >
                    <Trash2 size={14} aria-hidden="true" />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </Sheet>
  );
}
