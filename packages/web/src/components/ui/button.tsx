import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "jev";
type Size = "sm" | "md";

const variants: Record<Variant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700",
  secondary: "bg-surface text-ink border border-line hover:bg-canvas",
  ghost: "text-muted hover:bg-canvas hover:text-ink disabled:bg-transparent disabled:text-muted/50",
  danger: "bg-crit-500 text-white hover:bg-crit-700",
  jev: "bg-jev text-white hover:bg-jev/90",
};

// Filled buttons go flat grey when disabled, so they never read as clickable.
const DISABLED = "disabled:cursor-not-allowed disabled:border-transparent disabled:bg-line disabled:text-muted";

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-xs",
  md: "h-10 px-4 text-sm",
};

export function Button({
  variant = "primary",
  size = "md",
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors",
        DISABLED,
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}
