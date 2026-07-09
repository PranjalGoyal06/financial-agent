import type { Holding } from "../../lib/types";

const HOLDING_EXPORT_COLUMNS: Array<{
  header: string;
  value: (holding: Holding) => string | number | null | undefined;
}> = [
  { header: "ticker", value: (holding) => holding.raw_ticker },
  { header: "canonical_ticker", value: (holding) => holding.canonical_ticker },
  { header: "exchange", value: (holding) => holding.exchange },
  { header: "asset_class", value: (holding) => holding.asset_class },
  { header: "quantity", value: (holding) => holding.quantity },
  { header: "avg_buy_price", value: (holding) => holding.avg_buy_price },
  { header: "currency", value: (holding) => holding.currency },
  { header: "purchase_date", value: (holding) => holding.purchase_date },
];

function csvCell(value: string | number | null | undefined): string {
  if (value === null || value === undefined) {
    return "";
  }

  const text = String(value);
  if (!/[",\n\r]/.test(text)) {
    return text;
  }

  return `"${text.replace(/"/g, '""')}"`;
}

export function holdingsToCsv(holdings: Holding[]): string {
  const header = HOLDING_EXPORT_COLUMNS.map((column) => csvCell(column.header)).join(",");
  const rows = holdings.map((holding) =>
    HOLDING_EXPORT_COLUMNS.map((column) => csvCell(column.value(holding))).join(","),
  );

  return [header, ...rows].join("\n");
}

export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
