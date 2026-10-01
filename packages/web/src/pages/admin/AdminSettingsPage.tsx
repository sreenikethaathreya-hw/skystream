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

function SelectField<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: [T, string][];
  onChange: (v: T) => void;
}) {
  return (
    <label className="flex items-center justify-between gap-3 text-sm">
      <span className="text-muted">{label}</span>
      <select value={value} aria-label={label} onChange={(e) => onChange(e.target.value as T)}
        className="h-8 max-w-[260px] rounded-lg border border-line bg-surface px-2 text-sm">
        {options.map(([v, text]) => (
          <option key={v} value={v}>{text}</option>
        ))}
      </select>
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
          <SelectField label="Default display currency (figures are stored in net USD)" value={form.defaultDisplayCurrency}
            options={[["USD", "USD"], ["EUR", "EUR"], ["LOCAL", "Local currency"]]}
            onChange={(v) => setForm({ ...form, defaultDisplayCurrency: v })} />
          <SelectField label="Where reps' demand numbers come from" value={form.demandSource}
            options={[["ibp", "IBP forecast (SAC upload)"], ["manual", "Typed in Capture"]]}
            onChange={(v) => setForm({ ...form, demandSource: v })} />
        </CardBody>
      </Card>

      <Card className="xl:col-span-2" data-testid="assumption-settings">
        <CardHeader
          title="Data assumptions"
          subtitle="Defaults until the SMEs confirm. Changing one only affects uploads and checks from now on."
        />
        <CardBody className="grid gap-2 md:grid-cols-2">
          <SelectField label="Plan net price" value={form.priceSource}
            options={[["value_over_qty", "Sales Value / Sales Qty"], ["avg_net_price", "Avg Net Price column"]]}
            onChange={(v) => setForm({ ...form, priceSource: v })} />
          <SelectField label="Zero hectares in the market file" value={form.marketZeroMeans}
            options={[["no_market", "No market (skip segment)"], ["missing", "Data missing (show, no share checks)"]]}
            onChange={(v) => setForm({ ...form, marketZeroMeans: v })} />
          <SelectField label="Budget rate for past years" value={form.fxRateYearRule}
            options={[["same_year", "Each year's own budget rate"], ["current_budget", "Current budget rate"]]}
            onChange={(v) => setForm({ ...form, fxRateYearRule: v })} />
          <SelectField label="Score claims against" value={form.claimBaseline}
            options={[["plan", "The plan"], ["rep_number", "The rep's own number"]]}
            onChange={(v) => setForm({ ...form, claimBaseline: v })} />
          <NumberField label="Days before new actuals resolve claims" value={form.actualsHoldDays} step={1}
            onChange={(v) => setForm({ ...form, actualsHoldDays: v })} />
          <NumberField label="'No change' claim tolerance (%)" value={form.claimNeutralTolerancePct} step={1}
            onChange={(v) => setForm({ ...form, claimNeutralTolerancePct: v })} />
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
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={form.chatWritesAllowed} className="mt-1" aria-label="Allow chat changes"
              onChange={(e) => setForm({ ...form, chatWritesAllowed: e.target.checked })} />
            <span>
              Let the assistant make changes
              <span className="block text-xs text-muted">
                Reps can ask it to submit or justify their own number, and leads to decide on entries, leave notes and
                activate rules. It only uses the exact numbers and words the user types, one change per message, and every
                change is logged.
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
