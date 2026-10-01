import { NavLink } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import type { ChatCell, ChatLink, ChatSource } from "@/lib/types";

function cell(value: ChatCell, isYear = false): string {
  if (value === null) return "–";
  if (typeof value === "number") return isYear ? String(value) : value.toLocaleString("en-US");
  if (typeof value === "boolean") return value ? "yes" : "no";
  return value;
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
            <table className="w-full text-left text-xs">
              <thead>
                <tr>
                  {source.columns.map((column) => (
                    <th key={column} className="whitespace-nowrap border-b border-line py-1 pr-3 font-medium text-muted">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {source.rows.map((row, r) => (
                  <tr key={r} className="border-b border-line/60 last:border-0">
                    {row.map((value, c) => (
                      <td key={c} className="py-1 pr-3 align-top tabular-nums text-ink">
                        {cell(value, source.columns[c] === "Year" || row[0] === "Year")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
                <ArrowUpRight size={12} />
              </NavLink>
            ))}
        </div>
      )}
    </div>
  );
}
