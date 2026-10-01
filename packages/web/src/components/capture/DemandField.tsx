import { useState } from "react";
import { Pencil } from "lucide-react";
import { fmtNum, parseWhole } from "@/lib/format";
import { cn } from "@/lib/utils";

const SIZES = {
  hero: {
    box: "gap-3 rounded-lg border-2 px-4 shadow-[inset_0_1px_2px_rgb(22_33_26/0.06)] focus-within:ring-4",
    icon: "size-5",
    input: "w-full py-2 text-5xl leading-tight tracking-tight placeholder:text-3xl",
    unit: "text-sm",
  },
  compact: {
    box: "gap-1.5 rounded-md border px-2 focus-within:ring-2",
    icon: "size-3.5",
    input: "w-24 py-1 text-xl",
    unit: "text-xs",
  },
} as const;

/**
 * The demand number box. Several instances can edit the same value: each keeps what the user typed while it still
 * parses to `value`, and otherwise shows the formatted value, so an edit in one box shows up in the others.
 */
export function DemandField({
  value,
  onChange,
  size = "hero",
  label,
  testId,
  className,
}: {
  value: number;
  onChange: (value: number) => void;
  size?: keyof typeof SIZES;
  /** Accessible name when there is no visible label around the field. */
  label?: string;
  testId: string;
  className?: string;
}) {
  const [text, setText] = useState("");
  const shown = parseWhole(text) === value ? text : value ? fmtNum(value) : "";
  const s = SIZES[size];
  return (
    <span
      className={cn(
        "group flex cursor-text items-center border-ink/25 bg-surface transition-colors hover:border-ink/50 focus-within:border-brand-600 focus-within:ring-brand-600/15",
        s.box,
        className,
      )}
      onClick={(e) => e.currentTarget.querySelector("input")?.focus()}
    >
      <Pencil aria-hidden className={cn("shrink-0 text-muted group-focus-within:text-brand-600", s.icon)} />
      <input
        type="text"
        inputMode="numeric"
        name={size === "hero" ? "demand" : undefined}
        autoComplete="off"
        spellCheck={false}
        placeholder="Type demand"
        aria-label={label}
        data-testid={testId}
        value={shown}
        onChange={(e) => {
          setText(e.target.value);
          onChange(parseWhole(e.target.value));
        }}
        onBlur={() => setText(value ? fmtNum(value) : "")}
        className={cn(
          "font-num tabular min-w-0 flex-1 bg-transparent font-semibold placeholder:font-normal placeholder:text-muted/60 focus-visible:outline-none",
          s.input,
        )}
      />
      <span className={cn("shrink-0 font-medium text-muted", s.unit)}>KS</span>
    </span>
  );
}
