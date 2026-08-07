import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { transform } from "esbuild";

async function importTsModule(path) {
  const source = await readFile(path, "utf8");
  const result = await transform(source, {
    format: "esm",
    loader: "ts",
    sourcemap: "inline",
  });

  return import(`data:text/javascript;base64,${Buffer.from(result.code).toString("base64")}`);
}

test("stableListKey keeps duplicate list values unique", async () => {
  const { stableListKey } = await importTsModule("src/features/chat/renderKeys.ts");
  const values = ["repeat", "repeat", { item: "x", reason: "same" }, { item: "x", reason: "same" }];
  const keys = values.map((value, index) => stableListKey("evidence", value, index));

  assert.equal(new Set(keys).size, values.length);
});

test("holdingsToCsv exports holdings with escaped CSV cells", async () => {
  const { holdingsToCsv } = await importTsModule("src/features/portfolio/exportCsv.ts");
  const csv = holdingsToCsv([
    {
      holding_id: "h1",
      raw_ticker: "ACME, LTD",
      canonical_ticker: "ACME.NS",
      exchange: "NSE",
      asset_class: "equity",
      quantity: 12.5,
      avg_buy_price: 101.25,
      currency: "INR",
      purchase_date: "2026-06-01",
      created_at: "2026-06-01T00:00:00Z",
    },
    {
      holding_id: "h2",
      raw_ticker: "QUOTE\"CO",
      canonical_ticker: "QUOTE.NS",
      exchange: "NSE",
      asset_class: "equity",
      quantity: 2,
      avg_buy_price: 10,
      currency: "INR",
      purchase_date: "2026-06-02",
      created_at: "2026-06-02T00:00:00Z",
    },
  ]);

  assert.equal(
    csv,
    [
      "ticker,canonical_ticker,exchange,asset_class,quantity,avg_buy_price,currency,purchase_date",
      "\"ACME, LTD\",ACME.NS,NSE,equity,12.5,101.25,INR,2026-06-01",
      "\"QUOTE\"\"CO\",QUOTE.NS,NSE,equity,2,10,INR,2026-06-02",
    ].join("\n"),
  );
});
