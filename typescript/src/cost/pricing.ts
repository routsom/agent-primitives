import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { repoRootPath } from "../harness/schemas.js";
import type { TokenUsage } from "../providers/types.js";

/**
 * Deterministic USD cost from token usage, using the shared price table in specs/pricing.json.
 * This is what turns the token counts every span already carries into the dollar figures the
 * profiler dashboard shows and that a real cost budget would cap. Prices are estimates you edit
 * to match your contract - not billing truth.
 */
interface ModelPrice {
  inputPerMTok: number;
  outputPerMTok: number;
  cachedInputPerMTok?: number;
}

let table: Record<string, ModelPrice> | undefined;

function loadTable(): Record<string, ModelPrice> {
  if (!table) {
    const raw = JSON.parse(readFileSync(resolve(repoRootPath, "specs", "pricing.json"), "utf-8")) as Record<string, unknown>;
    table = Object.fromEntries(Object.entries(raw).filter(([k]) => !k.startsWith("_"))) as Record<string, ModelPrice>;
  }
  return table;
}

export function priceKey(provider: string, model: string): string {
  return `${provider}:${model}`;
}

/**
 * Cost in USD for one model call. `provider:model` keys the table; an unknown key costs 0 (the
 * dashboard flags it as an estimate). If the provider is the mock and MOCK_PRICE_AS is set, mock
 * tokens are priced at that real model's rate so offline demos show realistic numbers.
 */
export function computeCostUsd(provider: string, model: string, usage: TokenUsage): number {
  const t = loadTable();
  let key = priceKey(provider, model);
  if (provider === "mock" && process.env["MOCK_PRICE_AS"]) key = process.env["MOCK_PRICE_AS"];

  const price = t[key];
  if (!price) return 0;

  const cached = usage.cachedInputTokens ?? 0;
  const freshInput = Math.max(0, usage.inputTokens - cached);
  const cachedRate = price.cachedInputPerMTok ?? price.inputPerMTok;

  return (freshInput * price.inputPerMTok + cached * cachedRate + usage.outputTokens * price.outputPerMTok) / 1_000_000;
}
