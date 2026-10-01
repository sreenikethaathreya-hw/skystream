import type { ReactNode } from "react";

/** An empty or failed screen that says what to do next. */
export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-start gap-2 py-16">
      <h1 className="text-lg font-semibold">{title}</h1>
      {children && <p className="text-sm text-muted">{children}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
