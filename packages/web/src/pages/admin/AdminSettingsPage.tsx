import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { useSaveSettings } from "@/hooks/mutations";
import { useAdminSettings } from "@/hooks/queries";
import { useSession } from "@/hooks/useSession";
import type { AppSettings } from "@/lib/types";
import type { Thresholds } from "@/lib/mathTypes";

const THRESHOLD_FIELDS: { key: keyof Thresholds; label: string; step: number }[] = [
  { key: "shareHistoryMarginPts", label: "Share above history (pts)", step: 1 },
  { key: "shareJumpPts", label: "Share jump from one entry (pts)", step: 1 },
  { key: "monthSigmaMultiplier", label: "Month outlier (sigma)", step: 0.5 },
  { key: "minMonthSigmaPct", label: "Minimum month sigma (share of plan)", step: 0.05 },
  { key: "minMonthSigmaAbs", label: "Minimum month sigma (KS)", step: 10 },
  { key: "priceCarryingShare", label: "Price carrying (share of revenue change)", step: 0.05 },
  { key: "rangeWidthPct", label: "Range too wide (share of number)", step: 0.05 },
  { key: "priceBandPct", label: "Price band around history", step: 0.05 },
  { key: "marketTrendPct", label: "Market area trend", step: 0.01 },
];

function NumberField({ label, value, step, onChange }: { label: string; value: number; step: number; onChange: (v: number) => void }) {
  return (
    <label className="flex items-center justify-between gap-3 text-sm">
      <span className="text-muted">{label}</span>
      <input type="number" step={step} value={value} aria-label={label}
        onChange={(e) => onChange(Number(e.target.value))}
        className="tabular h-8 w-28 rounded-lg border border-line px-2 text-right" />
    </label>
  );
}

export function AdminSettingsPage() {
  const { user } = useSession();
  const { data } = useAdminSettings();
  const save = useSaveSettings();
  const toast = useToast();
  const [form, setForm] = useState<AppSettings | null>(null);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  if (user?.role !== "admin") return <p className="text-sm text-muted">Only admins can change settings.</p>;
  if (!form) return <p className="text-sm text-muted">Loading settings...</p>;

  const onSave = () =>
    save.mutate(form, {
      onSuccess: () => toast({ tone: "success", title: "Settings saved" }),
      onError: (e) => toast({ tone: "error", title: "Could not save", body: e.message }),
    });

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Card>
        <CardHeader title="Planning" />
        <CardBody className="flex flex-col gap-2">
          <NumberField label="Planning year" value={form.currentYear} step={1} onChange={(v) => setForm({ ...form, currentYear: v })} />
          <NumberField label="Grower hectare cap per row" value={form.growerHaCap} step={50} onChange={(v) => setForm({ ...form, growerHaCap: v })} />
          <label className="flex items-center justify-between gap-3 text-sm">
            <span className="text-muted">Currency</span>
            <input value={form.currency} maxLength={3} aria-label="Currency"
              onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })}
              className="h-8 w-28 rounded-lg border border-line px-2 text-right" />
          </label>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="AI" subtitle="Jev is TypeSafe's hosted API; Gemini runs inside this GCP project." />
        <CardBody className="flex flex-col gap-2">
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={form.externalAiAllowed} className="mt-1" aria-label="Allow Jev"
              onChange={(e) => setForm({ ...form, externalAiAllowed: e.target.checked })} />
            <span>
              Send justification text to Jev
              <span className="block text-xs text-muted">
                Only switch on once Syngenta has cleared sending rep text to TypeSafe. While off, claims are structured by
                Gemini (fallback) or the offline decider.
              </span>
            </span>
          </label>
          <NumberField label="Jev choice confidence before Gemini fallback" value={form.jevConfidenceThreshold} step={0.05}
            onChange={(v) => setForm({ ...form, jevConfidenceThreshold: v })} />
          <NumberField label="Jev score confidence before Gemini fallback" value={form.jevScoreConfidenceThreshold} step={0.05}
            onChange={(v) => setForm({ ...form, jevScoreConfidenceThreshold: v })} />
        </CardBody>
      </Card>

      <Card className="xl:col-span-2">
        <CardHeader title="Plausibility thresholds" subtitle="Applied on every keystroke in Capture and re-checked on submit." />
        <CardBody className="grid gap-2 md:grid-cols-2">
          {THRESHOLD_FIELDS.map((f) => (
            <NumberField key={f.key} label={f.label} value={form.thresholds[f.key]} step={f.step}
              onChange={(v) => setForm({ ...form, thresholds: { ...form.thresholds, [f.key]: v } })} />
          ))}
        </CardBody>
      </Card>

      <div className="flex justify-end xl:col-span-2">
        <Button onClick={onSave} disabled={save.isPending} data-testid="save-settings">
          Save settings
        </Button>
      </div>
    </div>
  );
}
