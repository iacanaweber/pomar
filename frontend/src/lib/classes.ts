/** Classes cuja compra o app resolve em COTAS: têm cotação, lote e ticker.
 *  A ordem é a que aparece na UI — do que pesa mais na carteira típica para o que pesa menos. */
export const INVESTABLE_CLASSES = ["STOCK", "FII", "ETF", "BDR"] as const;

/** A carteira alvo inteira. RENDA_FIXA tem peso e déficit como qualquer classe, mas os
 *  itens da cesta dela são TAGS DE INDEXADOR e a compra é manual, feita fora do app — por
 *  isso ela não entra em INVESTABLE_CLASSES nem na comparação atual × alvo por ticker. */
export const RENDA_FIXA = "RENDA_FIXA";
export const ALLOCATION_CLASSES = [...INVESTABLE_CLASSES, RENDA_FIXA] as const;

export type InvestableClass = (typeof INVESTABLE_CLASSES)[number];

export const CLASS_LABEL: Record<string, string> = {
  STOCK: "Ações",
  FII: "FIIs",
  ETF: "ETFs",
  BDR: "BDRs",
  RENDA_FIXA: "Renda fixa",
};

export const classLabel = (cls: string): string => CLASS_LABEL[cls] ?? cls;
