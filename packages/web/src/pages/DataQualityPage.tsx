import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { useDataQuality } from "@/hooks/queries";
import { humanize } from "@/lib/format";

const SECTION_TITLES: Record<string, string> = {
  sales: "MV360 Sales (Syngenta 5-year plan)",
  market: "MV360 Market (MAPS history)",
  competitors: "MV360 Competitors",
  grower: "Grower Potential (CRM)",
  hierarchy: "Product hierarchy",
  geo: "Spain Geo",
  scope: "Locked scope",
  anonymization: "Anonymization",
  synthetic: "Synthetic layers",
};

function render(value: unknown): string {
  if (Array.isArray(value)) return value.length ? value.join(", ") : "none";
  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([k, v]) => `${k}: ${String(v)}`)
      .join(" · ");
  }
  if (typeof value === "number") return value.toLocaleString("en-US");
  return String(value);
}

export function DataQualityPage() {
  const { data } = useDataQuality();
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold">Data quality</h1>
        <p className="text-sm text-muted">
          What the ingest found and fixed in the source spreadsheets before anything reached the tool.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data &&
          Object.entries(data).map(([section, values]) => (
            <Card key={section} data-testid={`dq-${section}`}>
              <CardHeader title={SECTION_TITLES[section] ?? humanize(section)} />
              <CardBody>
                <dl className="flex flex-col gap-1.5 text-sm">
                  {Object.entries(values).map(([key, value]) => (
                    <div key={key} className="flex justify-between gap-3 border-b border-line/60 pb-1 last:border-0">
                      <dt className="text-muted">{humanize(key.replace(/([A-Z])/g, " $1").toLowerCase())}</dt>
                      <dd className="tabular text-right font-medium">{render(value)}</dd>
                    </div>
                  ))}
                </dl>
              </CardBody>
            </Card>
          ))}
      </div>
    </div>
  );
}
