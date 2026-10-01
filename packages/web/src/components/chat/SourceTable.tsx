import { fmtDecimal } from "@/lib/format";
import type { ChatCell, ChatSource } from "@/lib/types";

// Identifiers and years read wrong with thousands separators ("2,432").
const PLAIN_COLUMN = /(year|segment|id)$/i;

function cell(value: ChatCell, column: string): string {
  if (value === null) return "–";
  if (typeof value === "number") return PLAIN_COLUMN.test(column) ? String(value) : fmtDecimal(value);
  if (typeof value === "boolean") return value ? "yes" : "no";
  return value;
}

/** A tool result table, shared by chat answers and pinned widgets. */
export function SourceTable({ source }: { source: ChatSource }) {
  return (
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
                {cell(value, source.columns[c] ?? "")}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
