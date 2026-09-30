import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastTone = "success" | "error" | "info";
interface Toast {
  id: number;
  title: string;
  body?: string;
  tone: ToastTone;
}

const ToastContext = createContext<(toast: Omit<Toast, "id">) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const dismiss = (id: number) => setToasts((all) => all.filter((t) => t.id !== id));
  const push = useCallback((toast: Omit<Toast, "id">) => {
    const id = Date.now() + Math.random();
    setToasts((all) => [...all, { ...toast, id }]);
    setTimeout(() => dismiss(id), 6000);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex w-96 flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            role="status"
            className={cn(
              "rounded-xl border bg-surface p-3 shadow-lg",
              t.tone === "success" && "border-brand-500/40",
              t.tone === "error" && "border-crit-500/40",
              t.tone === "info" && "border-info-500/40",
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-semibold">{t.title}</p>
              <button aria-label="Dismiss" onClick={() => dismiss(t.id)} className="text-muted hover:text-ink">
                <X size={14} />
              </button>
            </div>
            {t.body && <p className="mt-1 text-xs text-muted">{t.body}</p>}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
