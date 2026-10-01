import { useEffect, useState, type ComponentProps, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

const ARMED_MS = 4000;

/** First click arms the button and asks again; the second click within a few seconds runs the action. */
export function ConfirmButton({
  onConfirm,
  confirmLabel,
  children,
  ...props
}: Omit<ComponentProps<typeof Button>, "onClick"> & { onConfirm: () => void; confirmLabel: ReactNode }) {
  const [armed, setArmed] = useState(false);

  useEffect(() => {
    if (!armed) return;
    const timer = setTimeout(() => setArmed(false), ARMED_MS);
    return () => clearTimeout(timer);
  }, [armed]);

  return (
    <Button
      {...props}
      variant={armed ? "danger" : props.variant}
      aria-label={armed ? undefined : props["aria-label"]}
      onBlur={() => setArmed(false)}
      onClick={() => {
        if (!armed) return setArmed(true);
        setArmed(false);
        onConfirm();
      }}
    >
      {armed ? confirmLabel : children}
    </Button>
  );
}
