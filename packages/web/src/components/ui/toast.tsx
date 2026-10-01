import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastTone = "success" | "error" | "info";
interface Toast {
  id: number;
  title: string;
  body?: string;
  tone: ToastTone;
}

const TOAST_MS = 6000;

const ToastContext = createContext<(toast: Omit<Toast, "id">) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [paused, setPaused] = useState(false);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: number) => {
    clearTimeout(timers.current.get(id));
    timers.current.delete(id);
    setToasts((all) => all.filter((t) => t.id !== id));
  }, []);

  const push = useCallback((toast: Omit<Toast, "id">) => {
    setToasts((all) => [...all, { ...toast, id: Date.now() + Math.random() }]);
  }, []);

  useEffect(() => {
    if (paused) {
      timers.current.forEach(clearTimeout);
      timers.current.clear();
      return;
    }
    for (const t of toasts) {
      if (!timers.current.has(t.id)) timers.current.set(t.id, setTimeout(() => dismiss(t.id), TOAST_MS));
    }
  }, [toasts, paused, dismiss]);

  useEffect(() => {
    const all = timers.current;
    return () => all.forEach(clearTimeout);
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div
        className="fixed bottom-4 right-4 z-50 flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2"
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
        onFocus={() => setPaused(true)}
        onBlur={() => setPaused(false)}
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            role={t.tone === "error" ? "alert" : "status"}
            className={cn(
              "rounded-xl border bg-surface p-3 shadow-lg",
              t.tone === "success" && "border-brand-500/40",
              t.tone === "error" && "border-crit-500/40",
              t.tone === "info" && "border-info-500/40",
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <p className="min-w-0 break-words text-sm font-semibold">{t.title}</p>
              <button aria-label="Dismiss" onClick={() => dismiss(t.id)} className="rounded text-muted hover:text-ink">
                <X size={14} aria-hidden="true" />
              </button>
            </div>
            {t.body && <p className="mt-1 break-words text-xs text-muted">{t.body}</p>}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
